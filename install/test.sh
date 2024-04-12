#!/bin/sh

export TESTING=true
export CONFIG_FILE=tests/bullseye/config.txt
export CMDLINE_FILE=tests/bullseye/cmdline.txt
export GIT_DESCRIBE_TAGS=1.2.0-79-gf5280f32


reset_files() {
  git checkout $CONFIG_FILE
  git checkout $CMDLINE_FILE
}


reset_files
# this is expected to return a non-zero exit code and change both files
if python ../core/tools/blueos_startup_update/blueos_startup_update; then
  echo "Error: blueos_startup_update was expected to return a non-zero exit code."
  exit 1
fi

reset_files

# this is expected to return a zero exit code and change both files
./boards/bcm_27xx.sh

# this is expected to return a zero exit code and NOT change any files
GIT_DESCRIBE_TAGS=1.2.0-79-gf5280f32 python ../core/tools/blueos_startup_update/blueos_startup_update

reset_files
