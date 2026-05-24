import requests
import re
import sys
import json
import os

os.chdir(os.path.join(os.path.dirname(__file__), '..'))

BASE_URL = "https://cloud-images.ubuntu.com"
INSTALLER_SCRIPT = "install-ubuntu.sh"
STATUS_SCRIPT = "status.json"
README = "README.md"
CODE_NAME = "noble"
NAME = "22.04 LTS"

def fetch_all_versions():
    try:
        url = f"{BASE_URL}/{CODE_NAME}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        matches = re.findall(r'(\d{8})\/', r.text)
        if not matches:
            raise Exception(f"No versions found on page '{url}'.")
        return sorted(set(matches), reverse=True)
    except Exception as e:
        raise Exception(f"Failed to fetch available versions: {str(e)}")

def get_current_version(script_path):
    try:
        with open(script_path, "r") as f:
            content = f.read()
        match = re.search(r'release=(.+)?', content)
        if not match:
            raise Exception(f"Current version not found in '{script_path}'.")
        return match.group(1)
    except Exception as e:
        raise Exception(f"Failed to get current version from script: {str(e)}")

def fetch_latest_checksums(version):
    try:
        url = f"{BASE_URL}/{CODE_NAME}/{version}/SHA256SUMS"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        raw_checksums = r.text.strip().splitlines()
        expected_suffixes = ["arm64-root.tar.xz", "armhf-root.tar.xz"]
        filtered = []
        for line in raw_checksums:
            for suffix in expected_suffixes:
                if line.endswith(suffix):
                    filtered.append(line)
                    break
        if not filtered:
            raise Exception("No matching trusted checksums found.")
        return "\n".join(filtered)
    except Exception as e:
        raise Exception(f"Failed to fetch and filter latest checksums: {str(e)}")

def verify_rootfs_links(version, checksums_text):
    try:
        base_url = f"{BASE_URL}/{CODE_NAME}/{version}"
        for line in checksums_text.strip().splitlines():
            filename = line.strip().split("*")[1]
            url = f"{base_url}/{filename}"
            if requests.head(url, timeout=10).status_code != 200:
                raise Exception(f"File inaccessible: {filename}")
        print("[+] All required rootfs archives are accessible.")
    except Exception as e:
        raise Exception(f"Failed to verify rootfs archive links: {str(e)}")

def update_script(script_path, new_version, new_checksums):
    try:
        with open(script_path, "r") as f:
            content = f.read()
        content = re.sub(r'name="(.+)?"', f'name="{NAME}"', content)
        content = re.sub(r'code_name=(.+)?', f'code_name={CODE_NAME}', content)
        content = re.sub(r'release=(.+)?', f'release={new_version}', content)
        new_shasums_formatted = '\n\t\t'.join(new_checksums.splitlines())
        new_shasums_block = f'TRUSTED_SHASUMS=$(\n\tcat <<-EOF\n\t\t{new_shasums_formatted}\n\tEOF\n)'
        content = re.sub(r'TRUSTED_SHASUMS=\$\(([\s\S]+)?EOF\n\)', new_shasums_block, content)
        with open(script_path, "w") as f:
            f.write(content)
        print(f"[+] Updated {script_path} to {NAME} ({CODE_NAME}-{new_version}).")
    except Exception as e:
        raise Exception(f"Failed to update installer script: {str(e)}")

def update_status_json(status_path, status):
    try:
        with open(status_path, "w") as f:
            json.dump({"status": status}, f, indent=2)
        print(f"[+] Updated {status_path} to status '{status}'.")
    except Exception as e:
        print(f"[-] Failed to update {status_path}: {str(e)}")

def update_readme(readme_path, new_version):
    try:
        with open(readme_path, "r") as f:
            content = f.read()
        updated_content = re.sub(
            r'(<a href="https:\/\/cloud-images\.ubuntu\.com\/)([a-z]+\/\d{8})(">)',
            fr'\g<1>{CODE_NAME}/{new_version}\g<3>',
            content)
        if content != updated_content:
            with open(readme_path, "w") as f:
                f.write(updated_content)
            print(f"[+] Updated {readme_path} link to version '{new_version}'.")
    except Exception as e:
        raise Exception(f"Failed to update {readme_path}: {str(e)}")

def main():
    update_success = False
    try:
        selected_version = fetch_all_versions()[0]
        current_version = get_current_version(INSTALLER_SCRIPT)
        
        if current_version == selected_version:
            print("[*] RootFS is already up-to-date.")
            return

        print(f"[!] Updating from {current_version} to {selected_version}...")
        latest_checksums = fetch_latest_checksums(selected_version)
        verify_rootfs_links(selected_version, latest_checksums)
        update_script(INSTALLER_SCRIPT, selected_version, latest_checksums)
        update_readme(README, selected_version)
        update_success = True
    except Exception as e:
        print(f"[-] {e}")
    finally:
        status = f"Ubuntu {NAME} ({CODE_NAME}-{selected_version}) Available" if update_success else "Unavailable"
        update_status_json(STATUS_SCRIPT, status)
        if not update_success: sys.exit(1)

if __name__ == "__main__":
    main()
