import unittest
import sys
import os
from unittest.mock import patch, mock_open, MagicMock

# Add parent directory to path to import build_config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import build_config

class TestConfigBuilder(unittest.TestCase):

    def test_window_rule_conversion(self):
        """Test that legacy TOML window rules are converted to Hyprland 0.53+ syntax."""
        mock_data = {
            "rules": {
                "window": [
                    "float, class:^(MyFloatApp)$",
                    "pin, title:^(PinnedApp)$",
                    "suppressevent maximize, class:.*"
                ]
            }
        }
        
        with patch("tomllib.load", return_value=mock_data):
            with patch("builtins.open", mock_open()) as mocked_file:
                build_config.generate_user_conf()
                
                handle = mocked_file()
                written_content = "".join(call.args[0] for call in handle.write.mock_calls)
                
                # Check conversions
                self.assertIn("windowrule = match:class ^(MyFloatApp)$, float true", written_content)
                self.assertIn("windowrule = match:title ^(PinnedApp)$, pin true", written_content)
                self.assertIn("windowrule = match:class .*, suppressevent maximize", written_content)

    def test_bind_cleaning(self):
        """Test that upstream binds, monitors, and execs are disabled."""
        dummy_base = "monitor=,preferred,auto,1\nbind = SUPER, Q, exec, kitty\nbind=SUPER,C,killactive\nexec-once = waybar\ngeneral {\n    gaps_in = 5\n}"
        
        # Mock urllib to return our dummy base
        mock_response = MagicMock()
        mock_response.read.return_value = dummy_base.encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        
        with patch("urllib.request.urlopen", return_value=mock_response):
            with patch("builtins.open", mock_open()) as mocked_file:
                build_config.download_base()
                
                handle = mocked_file()
                written_content = "".join(call.args[0] for call in handle.write.mock_calls)
                
                # Verify binds are commented out
                self.assertIn("# [DISABLED BY HYPRDE] bind = SUPER, Q, exec, kitty", written_content)
                self.assertIn("# [DISABLED BY HYPRDE] bind=SUPER,C,killactive", written_content)
                self.assertIn("# [DISABLED BY HYPRDE] exec-once = waybar", written_content)
                # Verify other lines remain
                self.assertIn("gaps_in = 5", written_content)

    def test_syntax_correction(self):
        """Test that variable names like col_active_border are converted to col.active_border."""
        mock_data = {
            "general": {"border_size": 2, "col_active_border": "0xff0000"},
            "binds": {"normal": {"list": ["$mainMod, Q, exec, kitty"]}}
        }
        
        with patch("tomllib.load", return_value=mock_data):
            with patch("builtins.open", mock_open()) as mocked_file:
                build_config.generate_user_conf()
                
                handle = mocked_file()
                content = "".join(call.args[0] for call in handle.write.mock_calls)
                
                # Check header
                self.assertIn("# Generated from hyprde.toml", content)
                # Check Syntax correction (col_ -> col.)
                self.assertIn("col.active_border = 0xff0000", content)
                # Check Binds
                self.assertIn("bind = $mainMod, Q, exec, kitty", content)

if __name__ == '__main__':
    unittest.main()
