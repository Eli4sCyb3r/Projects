#!/bin/bash

# Define log file
LOG_FILE="/home/kali/Desktop/script_log.txt"

# Function to log messages
function LOG_MESSAGE() 
{
	
    local message="$1"
    echo "$(date +"%Y-%m-%d %H:%M:%S") - $message" >> "$LOG_FILE"
    
}

LOG_MESSAGE "Script execution started."

# 1.1 Install the needed applications.
# 1.2 If the applications are already installed, don’t install them again.

	read -p "[***] Please specify the IP address of the remote host:" IP
	read -p "[***] Please specify the username of the remote host:" USER
	echo -n "[***] Please specify the password to the remote host:"
	read -s PASS
	echo

LOG_MESSAGE "Connecting to remote host $IP with username $USER."

function LOCAL_ANON()
{
	cd /home/kali/Desktop/nipe
	sudo -S perl nipe.pl restart 
	sleep 2
	sudo -S perl nipe.pl restart
	sleep 2
	echo "[!] Local host is going anonymous:"
	sudo -S perl nipe.pl status
	sleep 1
	
	LOCAL_SPOOFED_IP=$(curl -s ipv4.wtfismyip.com/text)
	
	if [ "$(geoiplookup $LOCAL_SPOOFED_IP | grep IL)" ]; then
        LOG_MESSAGE "Local host is not anonymous. Exiting script."
        echo "[^^] Local host is not anonymous! Goodbye."
        exit
    else 
        LOG_MESSAGE "Local host is anonymous. Spoofed country: $(geoiplookup $LOCAL_SPOOFED_IP | awk '{print $(NF)}')"
        echo "[^^] Local host is anonymous, the spoofed country is: $(geoiplookup $LOCAL_SPOOFED_IP | awk '{print $(NF)}')"
    fi 
	
}

LOCAL_ANON

	sshpass -p $PASS scp /home/kali/Desktop/installations.sh $USER@$IP:/home/$USER/Desktop
	sshpass -p $PASS ssh -o StrictHostKeyChecking=no $USER@$IP bash /home/$USER/Desktop/installations.sh

# 1.3 Check if the network connection is anonymous; if not, alert the user and exit.

function REMOTE_ANON() 
{
    Ip=$(sshpass -p $PASS ssh -o StrictHostKeyChecking=no $USER@$IP curl -s ipv4.wtfismyip.com/text)
    
    if [ "$(geoiplookup $Ip | grep IL)" ]; then
        LOG_MESSAGE "Remote host is not anonymous. Exiting script."
        echo "[^^] Remote host is not anonymous! Goodbye."
        exit
    else 
        LOG_MESSAGE "Remote host is anonymous. Spoofed country: $(geoiplookup $Ip | awk '{print $(NF)}')"
        echo "[^^] Remote host is anonymous, the spoofed country is: $(geoiplookup $Ip | awk '{print $(NF)}')"
    fi 
}

# 1.5 Allow the user to specify the address to scan via remote server; save into a variable.

function RMT() 

# 2. Automatically Connect and Execute Commands on the Remote Server via SSH.
# 2.1 Display the details of the remote server (country, IP, and Uptime	).	

{
    RMT_IP=$(sshpass -p $PASS ssh -o StrictHostKeyChecking=no $USER@$IP ifconfig | grep broadcast | awk '{print $2}')
    echo "[^^] Remote host IP: $RMT_IP"
    sleep 1
    
    RMT_COUNTRY=$(sshpass -p $PASS ssh -o StrictHostKeyChecking=no $USER@$IP whois $IP | grep -i country | awk '{print $2}')
    sleep 1
    echo "[^^] Remote host country: $RMT_COUNTRY"
    
    RMT_UPTIME=$(sshpass -p $PASS ssh -o StrictHostKeyChecking=no $USER@$IP uptime | awk '{print $1 $2 $3 $4}' | sed 's/:/:/; s/up/ up /' )
    sleep 1
    echo "[^^] Remote host uptime: $RMT_UPTIME"
    
# 2.2 Get the remote server to check the Whois of the given address.

    read -p "[***] Please specify the IP/DMN address you would like to scan:" SCANNED_IP
    
    sshpass -p $PASS ssh -o StrictHostKeyChecking=no $USER@$IP "whois $SCANNED_IP > /home/$USER/Desktop/whois.txt"
    
# 2.3 Get the remote server to scan for open ports on the given address.
    
    sshpass -p $PASS ssh -o StrictHostKeyChecking=no $USER@$IP "nmap $SCANNED_IP -sV -p T:1-100 -oG /home/$USER/Desktop/nmap.txt -T4 >/dev/null"
    
# 3. Results.
# 3.1 Save the Whois and Nmap data into files on the local computer.

	sshpass -p $PASS scp $USER@$IP:/home/$USER/Desktop/nmap.txt /home/kali/Desktop/
	sshpass -p $PASS scp $USER@$IP:/home/$USER/Desktop/whois.txt /home/kali/Desktop/
	
	LOG_MESSAGE "WHOIS and Nmap data of: $SCANNED_IP , has been collected and saved into local host Desktop."

	sshpass -p $PASS ssh -o StrictHostKeyChecking=no $USER@$IP "rm /home/$USER/Desktop/nmap.txt /home/$USER/Desktop/whois.txt"

	LOG_MESSAGE "WHOIS and Nmap files deleted from remote server."
	
	echo "[!] Scanned address details has been saved on local host Desktop."
	sleep 1
	echo "[!] Scanned address whois details has been saved on local host Desktop."
	sleep 1
	echo "[!] Scanned address details has been deleted from the remote host."

}

REMOTE_ANON
RMT

# 3.2 Create a log and audit your data collecting.

LOG_MESSAGE "Executing data collection."

	sshpass -p $PASS ssh -o StrictHostKeyChecking=no $USER@$IP "sshpass -p kali sudo rm /var/log/auth.log >/dev/null 2>&1"
	
LOG_MESSAGE "Remote host auth.log file has been removed from the system."

LOG_MESSAGE "Script execution completed."
