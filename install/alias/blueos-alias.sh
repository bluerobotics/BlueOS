#!/usr/bin/env bash

bash_alias_blueos='
#BlueOS Aliases Starter
if [ -f /etc/blueos/.bash_aliases ]; then
    . /etc/blueos/.bash_aliases_blueos
fi
'

if grep -Fxq "#BlueOS Aliases Starter" ~/.bashrc; then
    echo "WARNING: Custom BlueOS bash aliases already exists in ~/.bashrc. Did not overwrite."
else
    echo "WARNING: Custom BlueOS bash aliases added"
    echo -e "\n$bash_alias_blueos" >> ~/.bashrc
fi
