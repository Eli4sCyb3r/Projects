#!/bin/bash

# Checking if the file can be analyzed in Volatility; if yes, run Volatility. (2.1)
# Finding the memory profile and saving it into a variable. (2.2)
# Displaying the running processes. (2.3)
# Displaying network connections. (2.4)
# Attempting to extract registry information. (2.5)
# Volatility Function. 

function VOLATILITY() 
{
    if [[ "$FILE" == *".mem"* ]]; then
        echo " [**] File format recognized as memory image. Proceeding with Volatility analysis..."
        PROFILE=$(./vol -f $FILE imageinfo 2>/dev/null | grep Profile | awk '{print $4}' | sed 's/,/ /g')
        ./vol -f $FILE --profile=$PROFILE pstree > /home/kali/Desktop/WF.results/Vol.Processes        
        echo " [!] Running processes has been saved in main directory on your Desktop."
        ./vol -f $FILE --profile=$PROFILE connscan > /home/kali/Desktop/WF.results/Vol.Net.Connections
        echo " [!] Network connections has been saved in main directory on your Desktop."
        ./vol -f $FILE --profile=$PROFILE hivelist > /home/kali/Desktop/WF.results/Vol.Hivelist
        echo " [!] Hivelist has been saved in main directory on your Desktop."
    else
        echo " [!] File format not recognized as memory image. Cannot analyze with Volatility. Exiting..."
        exit 1
    fi
}

# Checking if the current user is 'root'. (1.1)

if [ "$(whoami)" != "root" ]; then
    echo "Error: This script must be run as root" >&2
    exit 1
fi

# Asking the user to specify the desired file for investigation and checking its existence. (1.2)

read -p "Please insert the full path of the file you'd like to investigate:" FILE

if [ ! -f "$FILE" ]; then
    echo "Error: File '$FILE' does not exist" >&2
    exit 1
fi

# Creating functions to install any forensic tools if they are missing. (1.3)

# List of packages to check and install.

echo " [***] Checking your system for any missing forensic tools and installing them if necessary..."

sleep 1

PACKAGES=("bulk-extractor" "binwalk" "foremost" "libimage-exiftool-perl")

# Function to check if a package is installed.

function PACKAGE_CHECKING() 
{
    dpkg -s "$1" &> /dev/null
}

# Function to install a package.

function PACKAGE_INSTALLATION() 
{
    apt-get install -y "$1"
}

# Loop through the list of packages.

for package in "${PACKAGES[@]}"; do
    if ! PACKAGE_CHECKING "$package"; then
        echo " [#] $package is not installed. Installing..."
        PACKAGE_INSTALLATION "$package"
    else
        echo " [!] $package is already installed."
    fi
done

# Asking the user to specify which carving tools they would like to use and extracting data using the desired tool/s. (1.4)
# Saving the data into a directory on the desktop. (1.5)
# Attempting to extract network files, if any, and displaying the location and size to the user. (1.6)

echo -e "Please select the carving tool for the file investigation:\n 1) Binwalk\n 2) Foremost\n 3) Bulk_Extractor\n 4) Exiftool\n 5) All of the above\n 6) Volatility\n 9) EXIT"
read TOOLS
HOME=/home/kali/Desktop
mkdir $HOME/WF.results > /dev/null 2>&1

case $TOOLS in 

	1)
		echo "Using binwalk.."
		binwalk --run-as=root -e finder.dd -C $HOME/WF.results/Binwalk_results > /dev/null 2>&1
		echo " [**] Binwalk results has been saved on your Desktop!"
	;;
	
	2)
		echo " [^] Using foremost.."
		foremost $FILE -o $HOME/WF.results/Foremost_results > /dev/null 2>&1
		echo " [**] Foremost results has been saved on your Desktop!"
	;;
	
	3)
		echo " [^] Using bulk_extractor.."
		bulk_extractor $FILE -o $HOME/WF.results/Bulk_results > /dev/null 2>&1
		echo " [**] Bulk_extractor results has been saved on your Desktop!"
	;;
	
	4)
		echo " [^] Using Exiftool.."
		exiftool "$FILE" >> $HOME/WF.results/Exif.results 2>/dev/null
		echo " [**] Exiftool results has been saved on your Desktop!"
	;;
	
	5) 
		echo " [^] Using Binwalk.."
		binwalk --run-as=root -e finder.dd -C $HOME/WF.results/Binwalk_results > /dev/null 2>&1
		echo " [^] Using Foremost.."
		foremost $FILE -o $HOME/WF.results/Foremost_results > /dev/null 2>&1
		echo " [^] Using Bulk_extractor.."
		bulk_extractor $FILE -o $HOME/WF.results/Bulk_results > /dev/null 2>&1
		echo " [^] Using Exiftool.."
		exiftool "$FILE" >> $HOME/WF.results/Exif.results 2>/dev/null
		echo " [**] All carvers results has been saved on your Desktop!"
	;;
	
	6)
		VOLATILITY
	;;
	
	9) exit


esac

# Checking if any network-related files were found.

if [ -d "$HOME/WF.results/Bulk_results" ]; then
    pcap_files=$(find "$HOME/WF.results/Bulk_results" -type f -name "*.pcap")
    if [ -n "$pcap_files" ]; then
        echo " [**] Network files extracted: .pcap file found."
        while IFS= read -r pcap_file; do
            echo " [!] Location: $pcap_file"
            echo " [!] Size: $(du -h "$pcap_file" | cut -f1)"
        done <<< "$pcap_files"
    else
        echo " [!] No network files (.pcap) found."
    fi
else
    echo " [!] No network files found."
fi

# Checking if there is any human-readable content. (1.7)

echo " [***] Checking for human-readable content..."

# Running the strings command to extract printable strings from the file.

strings_output=$(strings "$FILE")

# Checking if any strings are extracted.

if [ -n "$strings_output" ]; then
    echo " [**] Human-readable content found !"
else
    echo " [!] No human-readable content found !"
fi

# Displaying general statistics (time of analysis, number of found files). (3.1)

echo "Analysis completed on: $(date)"
echo "Number of files found: $(find "/home/kali/Desktop/WF.results" -type f | wc -l)"

# Saving all the results into a report (name and location, files extracted, time of analysis and the size of the files). (3.2)

REPORT_FILE="$HOME/WF.results/Investigation_Report.txt"
echo "Analysis completed on: $(date)" > "$REPORT_FILE"
echo "Number of files found: $(find "$HOME/WF.results" -type f | wc -l)" >> "$REPORT_FILE"
echo "Size of files found:" >> "$REPORT_FILE"
find "$HOME/WF.results" -type f -exec du -h {} + >> "$REPORT_FILE"

echo "Report file has been saved in the main directory on your Desktop."

# Zipping the extracted files and the report file. (3.3)

echo " [***] Zipping the main directory..."
cd /home/kali/Desktop
zip -r "WF.results.zip" "WF.results" > /dev/null 2>&1
echo " [**] Main directory has been zipped into 'WF.results.zip'."

# Deleting the main directory from the Desktop.

rm -r ./WF.results





