# -*- coding: utf-8 -*-
import os
from pprint import pformat
import pyblish.api
from ayon_core.pipeline import publish
import hou


class ExtractHDA(publish.Extractor):

    order = pyblish.api.ExtractorOrder
    label = "Extract HDA"
    hosts = ["houdini"]
    families = ["hda"]

    def process(self, instance):
        self.log.info(pformat(instance.data))
        hda_node = hou.node(instance.data.get("instance_node"))
        hda_def = hda_node.type().definition()
        hda_options = hda_def.options()
        hda_options.setSaveInitialParmsAndContents(True)

        next_version = instance.data["anatomyData"]["version"]
        self.log.info("setting version: {}".format(next_version))
        hda_def.setVersion(str(next_version))
        hda_def.setOptions(hda_options)
        hda_def.save(hda_def.libraryFilePath(), hda_node, hda_options)

        if instance.data["creator_attributes"].get("use_project"):
            # Set TAB Menu location interactively
            # This shouldn't be needed if the Tool Location is saved in the HDA.
            tool_name = hou.shelves.defaultToolName(
                hda_def.nodeTypeCategory().name(), hda_def.nodeTypeName())
            hou.shelves.tool(tool_name).setToolLocations(
                ("AYON/{}".format(instance.context.data["projectName"]),))

        if "representations" not in instance.data:
            instance.data["representations"] = []

        file = os.path.basename(hda_def.libraryFilePath())
        staging_dir = os.path.dirname(hda_def.libraryFilePath())
        self.log.info("Using HDA from {}".format(hda_def.libraryFilePath()))

        representation = {
            'name': 'hda',
            'ext': 'hda',
            'files': file,
            "stagingDir": staging_dir,
        }
        instance.data["representations"].append(representation)
