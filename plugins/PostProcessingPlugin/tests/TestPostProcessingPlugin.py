# Copyright (c) 2020 Ultimaker B.V.
# Cura is released under the terms of the LGPLv3 or higher.

import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

from UM.PluginRegistry import PluginRegistry
from UM.Resources import Resources
from UM.Trust import Trust
from ..PostProcessingPlugin import PostProcessingPlugin

# not sure if needed
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

""" In this file, community refers to regular Cura for makers."""

mock_plugin_registry = MagicMock()
mock_plugin_registry.getPluginPath = MagicMock(return_value = "mocked_plugin_path")


# noinspection PyProtectedMember
@patch("cura.ApplicationMetadata.IsEnterpriseVersion", False)
def test_community_user_script_allowed():
    assert PostProcessingPlugin._isScriptAllowed("blaat.py")


# noinspection PyProtectedMember
@patch("cura.ApplicationMetadata.IsEnterpriseVersion", False)
def test_community_bundled_script_allowed():
    assert PostProcessingPlugin._isScriptAllowed(_bundled_file_path())


# noinspection PyProtectedMember
@patch("cura.ApplicationMetadata.IsEnterpriseVersion", True)
@patch.object(PluginRegistry, "getInstance", return_value=mock_plugin_registry)
def test_enterprise_unsigned_user_script_not_allowed(plugin_registry):
    assert not PostProcessingPlugin._isScriptAllowed("blaat.py")

# noinspection PyProtectedMember
@patch("cura.ApplicationMetadata.IsEnterpriseVersion", True)
@patch.object(PluginRegistry, "getInstance", return_value=mock_plugin_registry)
def test_enterprise_signed_user_script_allowed(plugin_registry):
    mocked_trust = MagicMock()
    mocked_trust.signedFileCheck = MagicMock(return_value=True)

    plugin_registry.getPluginPath = MagicMock(return_value="mocked_plugin_path")

    with patch.object(Trust, "signatureFileExistsFor", return_value = True):
        with patch("UM.Trust.Trust.getInstanceOrNone", return_value=mocked_trust):
            assert PostProcessingPlugin._isScriptAllowed("mocked_plugin_path/scripts/blaat.py")


# noinspection PyProtectedMember
@patch("cura.ApplicationMetadata.IsEnterpriseVersion", False)
def test_enterprise_bundled_script_allowed():
    assert PostProcessingPlugin._isScriptAllowed(_bundled_file_path())


def _bundled_file_path():
    return os.path.join(
        Resources.getStoragePath(Resources.Resources) + "scripts/blaat.py"
    )


def _make_plugin_instance():
    """Create a PostProcessingPlugin instance with all Qt/Application dependencies mocked."""
    mock_app = MagicMock()
    mock_stack = MagicMock()
    mock_stack.getMetaDataEntry = MagicMock(return_value=None)
    mock_app.getGlobalContainerStack = MagicMock(return_value=mock_stack)
    mock_app.getOutputDeviceManager = MagicMock(return_value=MagicMock())
    mock_app.globalContainerStackChanged = MagicMock()
    mock_app.mainWindowChanged = MagicMock()

    with patch("plugins.PostProcessingPlugin.PostProcessingPlugin.Application") as mock_application_cls, \
         patch("plugins.PostProcessingPlugin.PostProcessingPlugin.CuraApplication") as mock_cura_app_cls, \
         patch("PyQt6.QtCore.QObject.__init__", return_value=None), \
         patch("UM.Extension.Extension.__init__", return_value=None):
        mock_application_cls.getInstance = MagicMock(return_value=mock_app)
        mock_cura_app_cls.getInstance = MagicMock(return_value=mock_app)
        plugin = PostProcessingPlugin.__new__(PostProcessingPlugin)
        plugin._loaded_scripts = {}
        plugin._script_labels = {}
        plugin._script_list = []
        plugin._selected_script_index = -1
        plugin._global_container_stack = mock_stack
        plugin._view = None
        return plugin


def test_export_scripts_writes_valid_json():
    """exportScripts should write a valid JSON file with the correct structure."""
    plugin = _make_plugin_instance()

    # Build a fake script
    mock_script = MagicMock()
    mock_script.getSettingData = MagicMock(return_value={"key": "PauseAtHeight", "settings": {"pause_at": "10"}})
    mock_script.getSettingValueByKey = MagicMock(return_value="10")
    plugin._script_list = [mock_script]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".postprocessing", delete=False) as f:
        tmp_path = f.name

    try:
        mock_url = MagicMock()
        mock_url.toLocalFile = MagicMock(return_value=tmp_path)
        plugin.exportScripts(mock_url)

        with open(tmp_path, "r") as f:
            data = json.load(f)

        assert data["type"] == "postprocessing-script-config"
        assert data["version"] == 1
        assert len(data["scripts"]) == 1
        assert data["scripts"][0]["key"] == "PauseAtHeight"
        assert data["scripts"][0]["settings"]["pause_at"] == "10"
    finally:
        os.unlink(tmp_path)


def test_export_scripts_empty_list():
    """exportScripts with an empty script list should write a JSON with an empty scripts array."""
    plugin = _make_plugin_instance()
    plugin._script_list = []

    with tempfile.NamedTemporaryFile(mode="w", suffix=".postprocessing", delete=False) as f:
        tmp_path = f.name

    try:
        mock_url = MagicMock()
        mock_url.toLocalFile = MagicMock(return_value=tmp_path)
        plugin.exportScripts(mock_url)

        with open(tmp_path, "r") as f:
            data = json.load(f)

        assert data["type"] == "postprocessing-script-config"
        assert data["scripts"] == []
    finally:
        os.unlink(tmp_path)


def test_import_scripts_loads_scripts():
    """importScripts should populate _script_list from the JSON file."""
    plugin = _make_plugin_instance()

    mock_script_class = MagicMock()
    mock_script_instance = MagicMock()
    mock_script_instance._instance = MagicMock()
    mock_script_class.return_value = mock_script_instance
    plugin._loaded_scripts = {"PauseAtHeight": mock_script_class}

    export_data = {
        "version": 1,
        "type": "postprocessing-script-config",
        "scripts": [{"key": "PauseAtHeight", "settings": {"pause_at": "10"}}],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".postprocessing", delete=False) as f:
        json.dump(export_data, f)
        tmp_path = f.name

    try:
        mock_url = MagicMock()
        mock_url.toLocalFile = MagicMock(return_value=tmp_path)

        with patch.object(plugin, "loadAllScripts"), \
             patch.object(plugin, "setSelectedScriptIndex") as mock_set_idx, \
             patch.object(plugin, "scriptListChanged") as mock_signal, \
             patch.object(plugin, "_propertyChanged"):
            plugin.importScripts(mock_url)

        assert len(plugin._script_list) == 1
        assert plugin._script_list[0] is mock_script_instance
        mock_script_instance.initialize.assert_called_once()
    finally:
        os.unlink(tmp_path)


def test_import_scripts_wrong_type_ignored():
    """importScripts should skip files that do not have the correct type field."""
    plugin = _make_plugin_instance()

    bad_data = {"version": 1, "type": "something-else", "scripts": []}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".postprocessing", delete=False) as f:
        json.dump(bad_data, f)
        tmp_path = f.name

    try:
        mock_url = MagicMock()
        mock_url.toLocalFile = MagicMock(return_value=tmp_path)
        plugin.importScripts(mock_url)
        # Script list must not change
        assert plugin._script_list == []
    finally:
        os.unlink(tmp_path)


def test_import_scripts_unknown_key_skipped():
    """importScripts should skip entries whose script key is not in _loaded_scripts."""
    plugin = _make_plugin_instance()
    plugin._loaded_scripts = {}  # No loaded scripts

    export_data = {
        "version": 1,
        "type": "postprocessing-script-config",
        "scripts": [{"key": "UnknownScript", "settings": {}}],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".postprocessing", delete=False) as f:
        json.dump(export_data, f)
        tmp_path = f.name

    try:
        mock_url = MagicMock()
        mock_url.toLocalFile = MagicMock(return_value=tmp_path)

        with patch.object(plugin, "loadAllScripts"):
            plugin.importScripts(mock_url)

        assert plugin._script_list == []
    finally:
        os.unlink(tmp_path)


def test_clear_scripts_empties_list():
    """clearScripts should remove all scripts from _script_list."""
    plugin = _make_plugin_instance()

    mock_script = MagicMock()
    plugin._script_list = [mock_script]

    with patch.object(plugin, "setSelectedScriptIndex") as mock_set_idx, \
         patch.object(plugin, "scriptListChanged") as mock_signal, \
         patch.object(plugin, "_propertyChanged"):
        plugin.clearScripts()

    assert plugin._script_list == []

