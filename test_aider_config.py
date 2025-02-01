import os
import yaml

def find_and_read_aider_config():
    """Find and display aider configuration file contents"""
    # Common locations for aider.conf.yml
    possible_paths = [
        os.path.expanduser("~/.aider.conf.yml"),  # User home directory
        "aider.conf.yml",  # Current directory
    ]
    
    print("Searching for aider.conf.yml in:")
    for path in possible_paths:
        print(f"- {path}")
        if os.path.exists(path):
            print(f"Found aider config at: {path}")
            try:
                with open(path, 'r') as f:
                    config = yaml.safe_load(f)
                print("\nConfiguration contents:")
                print(yaml.dump(config, default_flow_style=False))
                return
            except Exception as e:
                print(f"Error reading config: {e}")
    
    print("No aider.conf.yml found in common locations")

if __name__ == "__main__":
    find_and_read_aider_config()
