import unittest
import sys
import os
import subprocess
import tomllib
import tempfile
from unittest.mock import patch, mock_open, MagicMock

# Add parent directory to path to import build_config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import build_config


class TestConfigBuilder(unittest.TestCase):
    """Comprehensive tests for the HyprDE configuration builder."""

    def setUp(self):
        # Mock atomic_write to avoid actual file system operations and path errors
        self.patcher = patch('build_config.atomic_write')
        self.mock_atomic_write = self.patcher.start()
        # Mock Waybar update to avoid JSON/path errors
        self.waybar_patcher = patch('build_config.update_waybar_autohide')
        self.mock_waybar = self.waybar_patcher.start()
        # Mock os.path.exists to ensure download_base logic runs
        self.exists_patcher = patch('os.path.exists', return_value=False)
        self.mock_exists = self.exists_patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.waybar_patcher.stop()
        self.exists_patcher.stop()

    def test_window_rule_conversion(self):
        """Test that legacy TOML window rules are converted to Hyprland 0.54+ block syntax."""
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
            build_config.generate_user_conf()
            
            # Check conversions to block syntax in atomic_write calls
            written_content = ""
            for call in self.mock_atomic_write.call_args_list:
                if call.args[0] == build_config.USER_CONF:
                    written_content = call.args[1]
                    break

            self.assertIn("windowrule {", written_content)
            self.assertIn("match:class = ^(MyFloatApp)$", written_content)
            self.assertIn("float = true", written_content)
            self.assertIn("match:title = ^(PinnedApp)$", written_content)
            self.assertIn("pin = true", written_content)
            self.assertIn("match:class = .*", written_content)
            self.assertIn("suppress_event = maximize", written_content)

    def test_bind_cleaning(self):
        """Test that upstream binds, monitors, and execs are disabled."""
        dummy_base = "monitor=,preferred,auto,1\nbind = SUPER, Q, exec, kitty\nbind=SUPER,C,killactive\nexec-once = waybar\ngeneral {\n    gaps_in = 5\n}"
        
        # Mock urllib to return our dummy base
        mock_response = MagicMock()
        mock_response.read.return_value = dummy_base.encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_response.headers = {'Content-Type': 'text/plain'}
        
        with patch("urllib.request.urlopen", return_value=mock_response):
             build_config.download_base()
             
             # Check if BASE_CONF was written with disabled binds
             written_content = ""
             for call in self.mock_atomic_write.call_args_list:
                 if call.args[0] == build_config.BASE_CONF:
                     written_content = call.args[1]
                     break
                
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
            build_config.generate_user_conf()
            
            written_content = ""
            for call in self.mock_atomic_write.call_args_list:
                if call.args[0] == build_config.USER_CONF:
                    written_content = call.args[1]
                    break
                
            # Check header
            self.assertIn("# Generated from hyprde.toml", written_content)
            # Check Syntax correction (col_ -> col.)
            self.assertIn("col.active_border = 0xff0000", written_content)
            # Check Binds
            self.assertIn("bind = $mainMod, Q, exec, kitty", written_content)


class TestHyprlandVersion(unittest.TestCase):
    """Tests for Hyprland version detection."""

    def setUp(self):
        # Clear version cache for clean tests
        self.cache_patcher = patch('pathlib.Path.exists', return_value=False)
        self.cache_patcher.start()

    def tearDown(self):
        self.cache_patcher.stop()

    @patch('subprocess.check_output')
    def test_get_version_from_tag(self, mock_output):
        """Test version extraction from 'Tag: vX.Y.Z' format."""
        mock_output.return_value = "Hyprland 0.40.0 built from branch main\nTag: v0.40.0"
        version = build_config.get_hyprland_version()
        self.assertEqual(version, "v0.40.0")

    @patch('subprocess.check_output')
    def test_get_version_from_name(self, mock_output):
        """Test version extraction from 'Hyprland X.Y.Z' format."""
        mock_output.return_value = "Hyprland 0.39.1 built from branch main"
        version = build_config.get_hyprland_version()
        self.assertEqual(version, "v0.39.1")

    @patch('subprocess.check_output')
    def test_get_version_not_found(self, mock_output):
        """Test fallback to 'main' when version not detected."""
        mock_output.side_effect = FileNotFoundError()
        version = build_config.get_hyprland_version()
        self.assertEqual(version, "main")

    @patch('subprocess.check_output')
    def test_get_version_command_failed(self, mock_output):
        """Test fallback to 'main' when Hyprland command fails."""
        mock_output.side_effect = subprocess.CalledProcessError(1, "Hyprland")
        version = build_config.get_hyprland_version()
        self.assertEqual(version, "main")


class TestDownloadFallback(unittest.TestCase):
    """Tests for download fallback behavior."""

    def setUp(self):
        self.patcher = patch('build_config.atomic_write')
        self.mock_atomic_write = self.patcher.start()
        # Mock exists to ensure download runs
        self.exists_patcher = patch('os.path.exists', return_value=False)
        self.mock_exists = self.exists_patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.exists_patcher.stop()

    @patch('urllib.request.urlopen')
    def test_download_success(self, mock_urlopen):
        """Test successful download with SSL and size validation."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"test config"
        mock_response.headers = {'Content-Type': 'text/plain'}
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        with patch("builtins.open", mock_open()) as mocked_file:
            build_config.download_base()
            mock_urlopen.assert_called_once()

    @patch('urllib.request.urlopen')
    @patch('os.path.exists')
    @patch('builtins.open', mock_open(read_data=b"fallback content"))
    def test_download_fallback(self, mock_exists, mock_urlopen):
        """Test fallback to local file when download fails."""
        mock_urlopen.side_effect = Exception("Network error")
        mock_exists.return_value = True
        
        # Should not raise exception, should use fallback
        build_config.download_base()

    def test_content_type_validation(self):
        """Test that invalid Content-Type is rejected."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"test"
        mock_response.headers = {'Content-Type': 'application/pdf'}
        mock_response.__enter__.return_value = mock_response
        
        with patch('urllib.request.urlopen', return_value=mock_response):
            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data=b"fallback")):
                    # Should fall back due to invalid content type
                    build_config.download_base()


class TestSectionGenerators(unittest.TestCase):
    """Tests for individual config section generators."""

    def setUp(self):
        self.patcher = patch('build_config.atomic_write')
        self.mock_atomic_write = self.patcher.start()
        # Mock Waybar update
        self.waybar_patcher = patch('build_config.update_waybar_autohide')
        self.mock_waybar = self.waybar_patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.waybar_patcher.stop()

    def test_monitors_section(self):
        """Test monitors section generation."""
        mock_data = {
            "monitors": {
                "rules": [
                    ", highres, auto, 1.0",
                    "HDMI-A-1, 1920x1080@120, auto, 1"
                ]
            }
        }
        
        with patch("tomllib.load", return_value=mock_data):
            build_config.generate_user_conf()
            
            written_content = ""
            for call in self.mock_atomic_write.call_args_list:
                if call.args[0] == build_config.USER_CONF:
                    written_content = call.args[1]
                    break
                
            self.assertIn("monitor = , highres, auto, 1.0", written_content)
            self.assertIn("monitor = HDMI-A-1, 1920x1080@120, auto, 1", written_content)

    def test_programs_section(self):
        """Test programs section generation."""
        mock_data = {
            "programs": {
                "terminal": "ghostty",
                "fileManager": "thunar"
            }
        }
        
        with patch("tomllib.load", return_value=mock_data):
            build_config.generate_user_conf()
            
            written_content = ""
            for call in self.mock_atomic_write.call_args_list:
                if call.args[0] == build_config.USER_CONF:
                    written_content = call.args[1]
                    break
                
            self.assertIn("$terminal = ghostty", written_content)
            self.assertIn("$fileManager = thunar", written_content)

    def test_autostart_section(self):
        """Test autostart section generation."""
        mock_data = {
            "autostart": {
                "exec_once": [
                    "waybar",
                    "mako"
                ]
            }
        }
        
        with patch("tomllib.load", return_value=mock_data):
            build_config.generate_user_conf()
            
            written_content = ""
            for call in self.mock_atomic_write.call_args_list:
                if call.args[0] == build_config.USER_CONF:
                    written_content = call.args[1]
                    break
                
            self.assertIn("exec-once = waybar", written_content)
            self.assertIn("exec-once = mako", written_content)

    def test_input_section(self):
        """Test input section generation."""
        mock_data = {
            "input": {
                "kb_layout": "us",
                "kb_options": "caps:escape",
                "follow_mouse": 1,
                "touchpad": {
                    "natural_scroll": False
                }
            }
        }
        
        with patch("tomllib.load", return_value=mock_data):
            build_config.generate_user_conf()
            
            written_content = ""
            for call in self.mock_atomic_write.call_args_list:
                if call.args[0] == build_config.USER_CONF:
                    written_content = call.args[1]
                    break
                
            self.assertIn("kb_layout = us", written_content)
            self.assertIn("kb_options = caps:escape", written_content)
            self.assertIn("follow_mouse = 1", written_content)
            self.assertIn("natural_scroll = false", written_content)


class TestHypridleGeneration(unittest.TestCase):
    """Tests for hypridle config generation."""

    def setUp(self):
        self.patcher = patch('build_config.atomic_write')
        self.mock_atomic_write = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_hypridle_basic(self):
        """Test basic hypridle config generation."""
        mock_data = {
            "idle": {
                "lock_timeout": 300,
                "screen_off_timeout": 330,
                "suspend_timeout": 1800
            }
        }
        
        build_config.generate_hypridle_conf(mock_data)
        
        written_content = ""
        for call in self.mock_atomic_write.call_args_list:
            if call.args[0] == build_config.HYPRIDLE_CONF:
                written_content = call.args[1]
                break
            
        self.assertIn("timeout = 300", written_content)
        self.assertIn("timeout = 330", written_content)
        self.assertIn("timeout = 1800", written_content)
        self.assertIn("lock_cmd = pidof hyprlock || hyprlock", written_content)

    def test_hypridle_no_idle_section(self):
        """Test that hypridle generation is skipped without idle section."""
        mock_data = {}
        
        with patch("builtins.open") as mocked_file:
            build_config.generate_hypridle_conf(mock_data)
            mocked_file.assert_not_called()


class TestSecurityValidation(unittest.TestCase):
    """Tests for security validation functions."""

    def test_validate_shell_safe_valid(self):
        """Test that valid shell values pass validation."""
        result = build_config.validate_shell_safe("/home/user/path", "test.field")
        self.assertEqual(result, "/home/user/path")

    def test_validate_shell_safe_invalid_semicolon(self):
        """Test that semicolons are rejected."""
        with self.assertRaises(ValueError):
            build_config.validate_shell_safe("path; rm -rf /", "test.field")

    def test_validate_shell_safe_invalid_pipe(self):
        """Test that pipes are rejected."""
        with self.assertRaises(ValueError):
            build_config.validate_shell_safe("path | cat", "test.field")

    def test_validate_shell_safe_invalid_dollar(self):
        """Test that dollar signs are rejected."""
        with self.assertRaises(ValueError):
            build_config.validate_shell_safe("$HOME/path", "test.field")


class TestAtomicWrite(unittest.TestCase):
    """Tests for atomic file write operations."""

    def test_atomic_write_success(self):
        """Test successful atomic write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            test_content = "test content"
            
            build_config.atomic_write(test_file, test_content)
            
            with open(test_file, 'r') as f:
                self.assertEqual(f.read(), test_content)

    def test_atomic_write_failure_cleanup(self):
        """Test that temp files are cleaned up on failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            # Make directory read-only to force failure
            os.chmod(tmpdir, 0o555)
            
            try:
                build_config.atomic_write(test_file, "content")
            except OSError:
                pass
            
            # Restore permissions for cleanup
            os.chmod(tmpdir, 0o755)
            
            # Check that temp file was cleaned up
            temp_pattern = f"{test_file}.tmp."
            temp_files = [f for f in os.listdir(tmpdir) if f.startswith(os.path.basename(temp_pattern))]
            self.assertEqual(len(temp_files), 0)


class TestErrorHandling(unittest.TestCase):
    """Tests for error handling paths."""

    def setUp(self):
        self.patcher = patch('build_config.atomic_write')
        self.mock_atomic_write = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_toml_file_not_found(self):
        """Test handling of missing TOML file."""
        with patch("tomllib.load", side_effect=FileNotFoundError()):
            with patch("builtins.open", mock_open()):
                # Should not raise exception, should log error and return
                build_config.generate_user_conf()

    def test_toml_decode_error(self):
        """Test handling of invalid TOML syntax."""
        with patch("tomllib.load", side_effect=tomllib.TOMLDecodeError("Invalid TOML", "", 0)):
            with patch("builtins.open", mock_open()):
                # Should not raise exception, should log error and return
                build_config.generate_user_conf()


class TestConfigValueFormatting(unittest.TestCase):
    """Tests for config value formatting."""

    def test_format_bool_true(self):
        """Test that True becomes 'true'."""
        result = build_config.format_config_value(True)
        self.assertEqual(result, "true")

    def test_format_bool_false(self):
        """Test that False becomes 'false'."""
        result = build_config.format_config_value(False)
        self.assertEqual(result, "false")

    def test_format_string(self):
        """Test string formatting."""
        result = build_config.format_config_value("test value")
        self.assertEqual(result, "test value")

    def test_format_integer(self):
        """Test integer formatting."""
        result = build_config.format_config_value(42)
        self.assertEqual(result, "42")


class TestGenerateConfigSection(unittest.TestCase):
    """Tests for the generate_config_section helper."""

    def test_basic_section_generation(self):
        """Test basic section generation."""
        lines = []
        data = {"key1": "value1", "key2": 42}
        
        build_config.generate_config_section(lines, "test", data)
        
        content = "\n".join(lines)
        self.assertIn("# Test", content)
        self.assertIn("test {", content)
        self.assertIn("key1 = value1", content)
        self.assertIn("key2 = 42", content)
        self.assertIn("}", content)

    def test_section_with_key_transform(self):
        """Test section generation with key transformation."""
        lines = []
        data = {"col_active": "0xff0000"}
        
        def transform(key):
            return key.replace("col_", "col.")
        
        build_config.generate_config_section(lines, "general", data, transform)
        
        content = "\n".join(lines)
        self.assertIn("col.active = 0xff0000", content)

    def test_section_skips_nested_dicts(self):
        """Test that nested dicts are skipped at top level."""
        lines = []
        data = {"key1": "value1", "nested": {"inner": "value"}}
        
        build_config.generate_config_section(lines, "test", data)
        
        content = "\n".join(lines)
        self.assertIn("key1 = value1", content)
        self.assertNotIn("nested", content)


class TestWallpaperSchedule(unittest.TestCase):
    """Tests for 3-slot wallpaper schedule generation."""

    def test_three_slot_schedule_generation(self):
        """Test that 3-slot schedule generates correctly."""
        mock_data = {
            "wallpapers": {
                "mode": "dynamic",
                "interval": 300,
                "schedule": {
                    "morning_start": "6:00 AM",
                    "noon_start": "12:00 PM",
                    "evening_start": "6:00 PM"
                },
                "directories": {
                    "morning": "sunrise",
                    "noon": "daylight",
                    "evening": "sunset"
                }
            }
        }
        
        with patch("build_config.atomic_write") as mock_write:
            build_config.generate_wallpaper_schedule_config(mock_data)
            
            mock_write.assert_called_once()
            content = mock_write.call_args[0][1]
            
            # Check 3 time slots
            self.assertIn('WALLPAPER_MORNING_START="06:00"', content)
            self.assertIn('WALLPAPER_NOON_START="12:00"', content)
            self.assertIn('WALLPAPER_EVENING_START="18:00"', content)
            
            # Check 3 directories
            self.assertIn('WALLPAPER_MORNING_DIR="sunrise"', content)
            self.assertIn('WALLPAPER_NOON_DIR="daylight"', content)
            self.assertIn('WALLPAPER_EVENING_DIR="sunset"', content)
            
            # Should NOT have night_start or night_dir
            self.assertNotIn("NIGHT_START", content)
            self.assertNotIn("NIGHT_DIR", content)

    def test_schedule_default_values(self):
        """Test that defaults are used when values missing."""
        mock_data = {
            "wallpapers": {
                "mode": "dynamic",
                "schedule": {},
                "directories": {}
            }
        }
        
        with patch("build_config.atomic_write") as mock_write:
            build_config.generate_wallpaper_schedule_config(mock_data)
            
            mock_write.assert_called_once()
            content = mock_write.call_args[0][1]
            
            # Check default time values
            self.assertIn('WALLPAPER_MORNING_START="06:00"', content)
            self.assertIn('WALLPAPER_NOON_START="12:00"', content)
            self.assertIn('WALLPAPER_EVENING_START="18:00"', content)
            
            # Check default directory values
            self.assertIn('WALLPAPER_MORNING_DIR="morning"', content)
            self.assertIn('WALLPAPER_NOON_DIR="noon"', content)
            self.assertIn('WALLPAPER_EVENING_DIR="evening"', content)

    def test_schedule_no_wallpapers_section(self):
        """Test that generation is skipped without wallpapers section."""
        mock_data = {}
        
        with patch("build_config.atomic_write") as mock_write:
            build_config.generate_wallpaper_schedule_config(mock_data)
            mock_write.assert_not_called()


class TestTimeConversion(unittest.TestCase):
    """Tests for time format conversion."""

    def test_12h_to_24h_conversion(self):
        """Test 12-hour to 24-hour time conversion."""
        self.assertEqual(build_config.convert_12h_to_24h("6:00 AM"), "06:00")
        self.assertEqual(build_config.convert_12h_to_24h("12:00 PM"), "12:00")
        self.assertEqual(build_config.convert_12h_to_24h("6:00 PM"), "18:00")
        self.assertEqual(build_config.convert_12h_to_24h("10:00 PM"), "22:00")
        self.assertEqual(build_config.convert_12h_to_24h("12:00 AM"), "00:00")

    def test_invalid_time_format(self):
        """Test that invalid time format raises ValueError."""
        with self.assertRaises(ValueError):
            build_config.convert_12h_to_24h("invalid")
        
        with self.assertRaises(ValueError):
            build_config.convert_12h_to_24h("25:00 AM")


if __name__ == '__main__':
    unittest.main(verbosity=2)
