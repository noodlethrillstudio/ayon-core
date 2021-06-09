import os
import six
import pyblish.api
import copy

from openpype.lib.plugin_tools import prepare_template_data


class IntegrateSlackAPI(pyblish.api.InstancePlugin):
    """ Send message notification to a channel.
        Triggers on instances with "slack" family, filled by
        'collect_slack_family'.
        Expects configured profile in
        Project settings > Slack > Publish plugins > Notification to Slack.
        If instance contains 'thumbnail' it uploads it. Bot must be present
        in the target channel.
        Message template can contain {} placeholders from anatomyData.
    """
    order = pyblish.api.IntegratorOrder + 0.499
    label = "Integrate Slack Api"
    families = ["slack"]

    optional = True

    def process(self, instance):
        message_templ = instance.data["slack_message"]

        fill_data = copy.deepcopy(instance.context.data["anatomyData"])
        self.log.debug("fill_data {}".format(fill_data))
        fill_pairs = (
            ("asset", fill_data["asset"]),
            ("subset", fill_data.get("subset", instance.data["subset"])),
            ("task", fill_data.get("task")),
            ("username", fill_data.get("username")),
            ("app", fill_data.get("app")),
            ("family", fill_data.get("family", instance.data["family"])),
            ("version", str(fill_data.get("version"))),
        )
        self.log.debug("fill_pairs {}".format(fill_pairs))
        multiple_case_variants = prepare_template_data(fill_pairs)
        fill_data.update(multiple_case_variants)
        self.log.debug("fill_data upd {}".format(fill_data))

        try:
            message = message_templ.format(**fill_data)
        except Exception:
            self.log.warning(
                "Some keys are missing in {}".format(message_templ),
                exc_info=True)
            return

        published_path = self._get_thumbnail_path(instance)

        for channel in instance.data["slack_channel"]:
            if six.PY2:
                self._python2_call(instance.data["slack_token"],
                                   channel,
                                   message,
                                   published_path)
            else:
                self._python3_call(instance.data["slack_token"],
                                   channel,
                                   message,
                                   published_path)

    def _get_thumbnail_path(self, instance):
        """Returns abs url for thumbnail if present in instance repres"""
        published_path = None
        for repre in instance.data['representations']:
            self.log.debug("repre ::{}".format(repre))
            if repre.get('thumbnail') or "thumbnail" in repre.get('tags', []):
                repre_files = repre["files"]
                if isinstance(repre_files, (tuple, list, set)):
                    filename = repre_files[0]
                else:
                    filename = repre_files

                published_path = os.path.join(
                    repre['stagingDir'], filename
                )
                break
        return published_path

    def _python2_call(self, token, channel, message, published_path):
        from slackclient import SlackClient
        try:
            client = SlackClient(token)
            if not published_path:
                response = client.api_call(
                    "chat.postMessage",
                    channel=channel,
                    text=message
                )
            else:
                response = client.api_call(
                    "files.upload",
                    channels=channel,
                    initial_comment=message,
                    file=published_path,
                )
            if response.get("error"):
                error_str = self._enrich_error(str(response.get("error")),
                                               channel)
                self.log.warning("Error happened: {}".format(error_str))
        except Exception as e:
            # You will get a SlackApiError if "ok" is False
            error_str = self._enrich_error(str(e), channel)
            self.log.warning("Error happened: {}".format(error_str))

    def _python3_call(self, token, channel, message, published_path):
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
        try:
            client = WebClient(token=token)
            if not published_path:
                _ = client.chat_postMessage(
                    channel=channel,
                    text=message
                )
            else:
                _ = client.files_upload(
                    channels=channel,
                    initial_comment=message,
                    file=published_path,
                )
        except SlackApiError as e:
            # You will get a SlackApiError if "ok" is False
            error_str = self._enrich_error(str(e.response["error"]), channel)
            self.log.warning("Error happened {}".format(error_str))

    def _enrich_error(self, error_str, channel):
        """Enhance known errors with more helpful notations."""
        if 'not_in_channel' in error_str:
            # there is no file.write.public scope, app must be explicitly in
            # the channel
            msg = " - application must added to channel '{}'.".format(channel)
            error_str += msg + " Ask Slack admin."
        return error_str
