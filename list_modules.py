import llama_index
import pkgutil

def list_modules(package, output_file):
    package_name = package.__name__
    with open(output_file, 'w') as f:
        for importer, modname, ispkg in pkgutil.walk_packages(path=package.__path__, prefix=package_name + "."):
            f.write(modname + "\n")

output_file = 'llama_index_modules.txt'
list_modules(llama_index, output_file)
print(f"Module list written to {output_file}")
