#!/bin/bash

REMOTE_REQUIREMENTS=( "curl" "cpanminus" "git" "nmap" "whois" "geoip-bin" "sshpass" )

function INSTALL_DEPENDENCIES()
{
    for package_name in "${REMOTE_REQUIREMENTS[@]}"; do
        dpkg -s "$package_name" >/dev/null 2>&1
        if [ $? -ne 0 ]; then
            echo "[*] Installing $package_name..."
            sudo -S apt-get install "$package_name" -y >/dev/null 2>&1
            if [ $? -eq 0 ]; then
                echo "[#] $package_name installed on remote host."
            else
                echo "[!] Failed to install $package_name."
            fi
        else
            echo "[#] $package_name is already installed on the remote host."
        fi
    done
}


function INSTALL_NIPE()
{
    cd /home/kali/Desktop/
    git clone https://github.com/htrgouvea/nipe >/dev/null 2>&1 && cd nipe
    cpanm --installdeps . >/dev/null 2>&1 
    sshpass -p kali sudo perl nipe.pl install 
    echo "[#] nipe installed on remote host."
}

function CHECK_NIPE()
{
    if [ ! -d /home/kali/Desktop/nipe ]
    then
        INSTALL_NIPE
    fi
}

function NIPE_ACTIVATION()
{
	
	cd /home/kali/Desktop/nipe/
	sudo -S perl nipe.pl restart 
	sleep 2
	sudo -S perl nipe.pl restart
	sleep 2
	echo "[!] Remote host is going anonymous:"
	sudo -S perl nipe.pl status
	
}

INSTALL_DEPENDENCIES
CHECK_NIPE
NIPE_ACTIVATION
