#!/usr/bin/bash

help_and_clean() {
	if [ "$1" == "help" ]
	then
		echo "Usage $0 [<if_running_minitune>] [<make_name>] [<Makefile_path>] [<compiling_command>]"
		echo "$0 clean OR $0 cleanall to delete [all the opentuner temp files] or [all the project runfiles]"
		echo "Default running Opentunner mini demo: True (input 0 to run the full flags)"
		echo "Default make file name: cloverleaf_tiled (hints: [cloverleaf_tiled, tealeaf_tiled, laplace2d_tiled])"
		echo "Default Makefile Location: ../CloverLeaf/"
		echo "Default compiling_command: /usr/bin/mpicxx (it should replace to your own mpicxx or gcc/g++)"
		exit 1
	
	elif [ "$1" == "clean" ]
	then
		echo "Cleaning up the opentuner tmp files"
		if [ -d "opentuner.db" ]; then
			rm -rf opentuner.db
		fi
		if [ -d "tmp" ]; then
			rm -rf tmp*
		fi
		if [ -f "opentuner.log" ]; then
			rm opentuner.log
		fi
		echo "Clean Done!"
		exit 1
	
	elif [ "$1" == "cleanall" ]
	then
		echo "Clean all files (*.in, *.out, *.json), recover to the very beginning stage"
	    if compgen -G "*.in" > /dev/null; then
			rm -f *.in
		fi
		if compgen -G "*.out" > /dev/null; then
			rm -f *.out
		fi
		if compgen -G "*.json" > /dev/null; then
			rm -f *.json
		fi
		if compgen -G "tmp*" > /dev/null; then
			rm -f tmp*
		fi
		echo "Clean Done!"
		exit 1
	fi
}

help_and_clean $1

RUNMINI=${1:-1}
FILENAME=${2:-cloverleaf_tiled}
MAKEPATH=${3:-../CloverLeaf/}
CC=${4:-/usr/bin/mpicxx}
JSONFILE="${FILENAME}_tunebase.json"

if [ -z "$3" ] && [ ! -z "$2" ]
then
	unset MAKEPATH
	if [ $2 = "tealeaf_tiled" ]
	then
		MAKEPATH=../TeaLeaf/
	elif [ $2 = "laplace2d_tiled" ]
	then
		MAKEPATH=../laplace2d_tutorial/step7/
	else
		exit 1
	fi
fi

# laplace2d requires cleaning the exe first, assuming all others are the same
make clean -C $MAKEPATH
TARGET=$(make -n $FILENAME -C $MAKEPATH)
rest_of_target=$(echo $TARGET | awk -v cc="$CC" '{sub(".*" cc, ""); print}')


# If the rest_of_target is empty, the compiling command was not found
if [ -z "$rest_of_target" ]; then
    echo "Compiling command not found in TARGET"
    exit 1
fi

# A hack for the kernels, serving as one of the passing parameters for tuning the full programme
kernels=$(echo "")

# Extracting the required flags with `-`, omit the O[0-3] as opentuner will tune automatically
flags=$(echo $rest_of_target | grep -oP ' -[^ILo]\S*' | grep -Ev ' -O[0-3]')
# echo "Flags: $flags"

# Extracting the include path with `-I`
ESCAPEDPATH=$(echo "$MAKEPATH" | sed 's/\//\\\//g')
include_paths=$(echo $rest_of_target | grep -oP ' -I\S+')
include_paths_array=($(echo "$include_paths" | sed 's/^ *//;s/ *$//' | sed "s/^-I.$/-I$ESCAPEDPATH/"))
# echo "Include paths: $include_paths"

# Extracting the directory dir with `-L`
directories=$(echo $rest_of_target | grep -oP ' -L\S+')
directories_array=($(echo "$directories" | sed 's/^ *//;s/ *$//'))
# echo "Directories: $directories"

# Extracting the linking files (anything without `-` before it, and not starting with a `/`)
linking_files=$(echo $rest_of_target | grep -oP ' (?<!-)([\w\./]+\.cpp\b)')
linking_files_array=($(echo "$linking_files" | sed 's/^ *//;s/ *$//'))
# echo "Linking files: $linking_files"

# Extracting the output file name, [DEBUG only]
output_file=$(echo $rest_of_target | grep -oP ' -o \K\S+')
# echo "Output file: $output_file"

# Write to JSON file
json_content=$(jq -n \
    --argjson kernel_files "$(printf '%s\n' "${kernels[@]}" | jq -R . | jq -s .)" \
    --argjson basic_params "$(printf '%s' "${flags[@]}" | jq -R . | jq -s .)" \
    --argjson include_path "$(printf '%s\n' "${include_paths_array[@]}" | jq -R . | jq -s .)" \
    --argjson linking_path "$(printf '%s\n' "${directories_array[@]}" | jq -R . | jq -s .)" \
    --argjson linking_files "$(printf '%s\n' "${linking_files_array[@]}" | jq -R . | jq -s .)" \
    '{kernel_files: $kernel_files, basic_params: $basic_params, include_path: $include_path, linking_path: $linking_path, linking_files: $linking_files}')
echo $json_content > $JSONFILE
echo $JSONFILE Saved!

## Run the Opentuner file
if [ $RUNMINI = 1 ]
then
	echo "----- Running the minimal tuning for $FILENAME -----"
	python3 ${FILENAME}_tune_minimal.py --stop-after=500 --no-dups 
else
	echo "----- Running the full tuning for $FILENAME -----"
	python3 tune_full.py $JSONFILE --no-dups --run-dir $MAKEPATH --cc $CC --early-time 0.000001
fi
