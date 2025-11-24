"""
起動時の環境チェックとセットアップ
"""
import sys
import subprocess
import shutil
from pathlib import Path


class StartupChecker:
    """起動時の環境チェッククラス"""

    def __init__(self):
        self.issues = []
        self.warnings = []
        self.missing_packages = []  # 不足パッケージのリスト

    def check_all(self):
        """全ての環境チェックを実行"""
        print("\n" + "="*60)
        print("Claude Code Monitor - Startup Check")
        print("="*60)

        self.check_python_version()
        self.check_python_packages()
        self.check_voicevox()

        return len(self.issues) == 0

    def check_python_version(self):
        """Pythonバージョンをチェック"""
        print("\n[1/3] Checking Python version...")
        version = sys.version_info

        if version.major < 3 or (version.major == 3 and version.minor < 8):
            self.issues.append("Python 3.8以降が必要です")
            print(f"  ✗ Python {version.major}.{version.minor}.{version.micro} (requires 3.8+)")
            return False
        else:
            print(f"  ✓ Python {version.major}.{version.minor}.{version.micro}")
            return True

    def check_python_packages(self):
        """必要なPythonパッケージをチェック"""
        print("\n[2/3] Checking Python packages...")

        # パッケージとその検証方法を定義
        required_packages = {
            'pyaudio': ('PyAudio', lambda m: hasattr(m, 'PyAudio')),
            'requests': ('requests', lambda m: hasattr(m, 'get') and hasattr(m, 'post')),
            'anthropic': ('anthropic', lambda m: hasattr(m, 'Anthropic'))
        }

        missing_packages = []

        for module_name, (pip_name, validator) in required_packages.items():
            try:
                module = __import__(module_name)
                # モジュールの主要機能が存在するか検証
                if not validator(module):
                    raise ImportError(f"{module_name} is not properly installed")
                print(f"  ✓ {pip_name}")
            except (ImportError, AttributeError) as e:
                print(f"  ✗ {pip_name} (not installed or incomplete)")
                missing_packages.append(pip_name)

        if missing_packages:
            print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
            self.missing_packages = missing_packages
            # GUIで許可を求めるため、ここではリストを保存するだけ
            return True  # チェック自体は成功

        return True

    def _install_packages(self, packages):
        """パッケージを自動インストール"""
        print("\nInstalling packages...")

        # PyAudioは特別な処理が必要な場合がある
        if 'PyAudio' in packages:
            print("\nNote: PyAudio may require portaudio")
            print("If installation fails, run: brew install portaudio")

        try:
            for package in packages:
                print(f"\nInstalling {package}...")
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', package],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    print(f"  ✓ {package} installed successfully")
                else:
                    print(f"  ✗ Failed to install {package}")
                    print(f"  Error: {result.stderr}")
                    self.issues.append(f"{package}のインストールに失敗しました")
                    return False

            print("\n✓ All packages installed successfully!")
            return True

        except Exception as e:
            print(f"\n✗ Installation error: {e}")
            self.issues.append(f"パッケージのインストール中にエラーが発生しました: {e}")
            return False

    def check_voicevox(self):
        """VOICEVOX Engineの状態をチェック"""
        print("\n[3/3] Checking VOICEVOX Engine...")

        try:
            import requests
            response = requests.get('http://localhost:50021/version', timeout=2)
            if response.status_code == 200:
                version_info = response.json()
                print(f"  ✓ VOICEVOX Engine running (version: {version_info})")
                return True
        except:
            pass

        print("  ⚠️  VOICEVOX Engine not running (optional)")
        print("     To use VOICEVOX TTS:")
        print("     1. Download from https://voicevox.hiroshiba.jp/")
        print("     2. Start VOICEVOX Engine application")
        self.warnings.append("VOICEVOX Engineが起動していません（オプション機能）")
        return True  # オプションなのでエラーにはしない

    def print_summary(self):
        """チェック結果のサマリーを表示"""
        print("\n" + "="*60)
        print("Summary")
        print("="*60)

        if not self.issues and not self.warnings:
            print("✓ All checks passed!")
            return True

        if self.warnings:
            print("\nWarnings:")
            for warning in self.warnings:
                print(f"  ⚠️  {warning}")

        if self.issues:
            print("\nErrors:")
            for issue in self.issues:
                print(f"  ✗ {issue}")
            print("\nPlease resolve the errors above before running the application.")
            return False

        return True


def run_startup_check():
    """起動チェックを実行"""
    checker = StartupChecker()
    success = checker.check_all()
    checker.print_summary()

    if not success:
        print("\n" + "="*60)
        input("Press Enter to exit...")
        sys.exit(1)

    print("\n" + "="*60)
    print("Starting Claude Code Monitor...")
    print("="*60 + "\n")

    return checker  # checkerオブジェクトを返す（missing_packagesを含む）


if __name__ == "__main__":
    run_startup_check()
