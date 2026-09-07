"""
Tests for GUI main module.

This module requires tkinter, so tests are skipped if tkinter is not available.
"""

import pytest


tkinter = pytest.importorskip("tkinter", reason="tkinter not available")
tk = tkinter


class TestManualProcessorGUIBasic:
    """Basic GUI tests with tkinter available"""

    def test_import_module(self):
        """Test that the gui module can be imported"""
        from src.gui.main import ManualProcessorGUI
        assert ManualProcessorGUI is not None

    def test_gui_class_structure(self):
        """Test that ManualProcessorGUI has expected attributes"""
        from src.gui.main import ManualProcessorGUI
        assert hasattr(ManualProcessorGUI, '__init__')

    def test_gui_inherits_from_tk(self):
        """Test that ManualProcessorGUI inherits from tk.Tk"""
        from src.gui.main import ManualProcessorGUI
        assert issubclass(ManualProcessorGUI, tk.Tk)
