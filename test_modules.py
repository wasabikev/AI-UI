import sys
import pkg_resources

def list_installed_packages():
    print("Python version:", sys.version)
    print("\nInstalled packages:")
    for dist in pkg_resources.working_set:
        print(f"{dist.key} - Version: {dist.version}")

if __name__ == "__main__":
    list_installed_packages()
