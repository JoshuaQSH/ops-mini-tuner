import sys
import json

def create_json(kernels, flags, include_paths, linking_paths, linking_files, output_file, make_path):
    include_paths = ["-I" + make_path if path == "-I." else path for path in include_paths]
    linking_paths = ["-L" + make_path if path == "-L." else path for path in linking_paths]

    data = {
        "kernel_files": kernels,
        "basic_params": flags,
        "include_path": include_paths,
        "linking_path": linking_paths,
        "linking_files": linking_files,
    }

    with open(output_file, 'w') as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    kernels = sys.argv[1].split()
    flags = sys.argv[2].split()
    include_paths = sys.argv[3].split()
    linking_paths = sys.argv[4].split()
    linking_files = sys.argv[5].split()
    output_file = sys.argv[6]
    make_path = sys.argv[7]
    create_json(kernels, flags, include_paths, linking_paths, linking_files, output_file, make_path)

