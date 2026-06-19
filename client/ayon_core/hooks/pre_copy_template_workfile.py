import os
import shutil

from ayon_core.settings import get_project_settings

from ayon_core.pipeline.template_data import get_template_data
from ayon_core.pipeline.workfile import (
    get_custom_workfile_template,
    get_custom_workfile_template_by_string_context,
    save_workfile_info,
    find_workfile_rootless_path,
    get_last_workfile_with_version_from_paths,
    get_workfile_template_key,
)

from ayon_applications import PreLaunchHook, LaunchTypes


class CopyTemplateWorkfile(PreLaunchHook):
    """Copy workfile template.

    This is not possible to do for all applications the same way.

    Prelaunch hook works only if last workfile leads to not existing file.
        - That is possible only if it's first version.
    """

    # Before `AddLastWorkfileToLaunchArgs`
    order = 0
    app_groups = {"blender", "photoshop", "animate", "tvpaint", "aftereffects",
                  "wrap"}
    launch_types = {LaunchTypes.local}

    def execute(self):
        """Check if can copy template for context and do it if possible.

        First check if host for current project should create first workfile.
        Second check is if template is reachable and can be copied.

        Args:
            last_workfile(str): Path where template will be copied.

        Returns:
            None: This is a void method.
        """

        last_workfile = self.data.get("last_workfile_path")
        if not last_workfile:
            self.log.warning((
                "Last workfile was not collected."
                " Can't add it to launch arguments or determine if should"
                " copy template."
            ))
            return

        if os.path.exists(last_workfile):
            self.log.debug("Last workfile exists. Skipping {} process.".format(
                self.__class__.__name__
            ))
            return

        self.log.info("Last workfile does not exist.")

        project_name = self.data["project_name"]
        folder_path = self.data["folder_path"]
        task_name = self.data["task_name"]
        host_name = self.application.host_name

        project_settings = get_project_settings(project_name)

        project_entity = self.data.get("project_entity")
        folder_entity = self.data.get("folder_entity")
        task_entity = self.data.get("task_entity")
        anatomy = self.data.get("anatomy")
        if project_entity and folder_entity and task_entity:
            self.log.debug("Started filtering of custom template paths.")
            template_path = get_custom_workfile_template(
                project_entity,
                folder_entity,
                task_entity,
                host_name,
                anatomy,
                project_settings
            )

        else:
            self.log.warning((
                "Global data collection probably did not execute."
                " Using backup solution."
            ))
            template_path = get_custom_workfile_template_by_string_context(
                project_name,
                folder_path,
                task_name,
                host_name,
                anatomy,
                project_settings
            )

        if not template_path:
            self.log.info(
                "Registered custom templates didn't match current context."
            )
            return

        if not os.path.exists(template_path):
            self.log.warning(
                "Couldn't find workfile template file \"{}\"".format(
                    template_path
                )
            )
            return

        self.log.info(
            f"Creating workfile from template: \"{template_path}\""
        )

        # Keep extension of template file
        _, ext = os.path.splitext(template_path)
        last_workfile_extless, _ = os.path.splitext(last_workfile)
        last_workfile = f"{last_workfile_extless}{ext}"

        # Copy template workfile to new destination
        shutil.copy2(
            os.path.normpath(template_path),
            os.path.normpath(last_workfile)
        )
        if not os.path.exists(os.path.normpath(last_workfile)):
            self.log.warning(
                "Couldn't copy template workfile to \"{}\"".format(
                    last_workfile
                )
            )
            return
        self._save_new_workfile(
            last_workfile,
            project_name,
            host_name,
            folder_entity,
            task_entity,
            project_entity,
            project_settings,
            anatomy
        )
        
    def _save_new_workfile(self, last_workfile, project_name, host_name, folder_entity, task_entity, project_entity, project_settings, anatomy):
        host_settings = project_settings.get(host_name)
        if not host_settings:
            self.log.info((
                "No settings for host \"{}\". Can't access custom templates"
                " in it."
            ).format(host_name))
            return
        workfile_builder_settings = host_settings.get("workfile_builder")
        if not workfile_builder_settings:
            self.log.info((
                "Seems like old version of settings is used."
                " Can't access custom templates in host \"{}\"."
            ).format(host_name))
            return

        if not workfile_builder_settings.get("save_new_workfile", False):
            self.log.info((
                "Saving new workfile after copying template is disabled in"
                " settings. New workfile won't be saved to Ayon."
            ))
            return
        
        rootless_path = find_workfile_rootless_path(
            workfile_path=last_workfile,
            project_name=project_name,
            folder_entity=folder_entity,
            task_entity=task_entity,
            host_name=host_name,
            project_entity=project_entity,
            project_settings=project_settings,
            anatomy=anatomy,
        )

        save_workfile_info(
            project_name=project_name,
            task_id=task_entity["id"],
            rootless_path=rootless_path,
            host_name=host_name
        )
