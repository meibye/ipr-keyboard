#!/bin/bash
#
# scmd.sh - Script Command Menu
#
# List and execute scripts in the ipr-keyboard scripts directory.
# Provides a hierarchical menu system based on script prefixes.
#
# Usage:
#    ./scripts/scmd.sh [-c <comma-separated list of categories>] [-e <comma-separated list of scripts>]
#
# Options:
#   -c <categories>  Comma-separated list of categories to exclude from menu
#   -e <scripts>     Comma-separated list of specific scripts to exclude from menu
#
# Scripts are organized by prefix (before first underscore):
#   - ble_    : Bluetooth configuration and management
#   - dev_    : Development tools
#   - diag_   : Diagnostics and troubleshooting
#   - env_    : Environment configuration
#   - sys_    : System setup and packages
#   - test_   : Testing scripts
#   - usb_    : USB/MTP mounting
#   - service/: Service management (subdirectory)
#   - extras/ : BLE extras (subdirectory)
#
# Script metadata is read from comment headers:
#   # category: <category_name>
#   # purpose: <brief_description>
#   # parameters: <param1>,<param2>,...
#
# category: Tools
# purpose: Interactive menu for executing scripts

set -eo pipefail

# Color codes for output
BYellow='\033[1;33m'
BBlue='\033[1;34m'
BRed='\033[1;31m'
BGreen='\033[1;32m'
Color_Off='\033[0m'

#
# Determine directory name of script
#
SCRIPT_DIR=$(cd "$(dirname "$0" )" >/dev/null 2>&1 && pwd)
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

#
# Save the current directory
#
CURRENT_DIR=$PWD

#
# Repeat given char N times using shell function
#
repeat() {
	local start=1
	local end=${1:-80}
	local str="${2:-=}"
	local range=$(seq $start $end)
	for i in $range ; do echo -n "${str}"; done
}

# ==================================================================================
# Function to check if input is a valid number
is_valid_number() {
    local input="$1"
    if [[ "$input" =~ ^[0-9]+$ ]]; then
        return 0  # Valid number
    else
        return 1  # Not a valid number
    fi
}

# ==================================================================================
# Function to get script category from comments
get_category() {
    script="$1"
    if [ -f "$script" ]; then
        # Match both '# category:' and '#  category:'
        category=$(grep -m 1 -E "^[[:space:]]*# ? ?category:.*" "$script" | sed -E 's/^[[:space:]]*# ? ?category:[[:space:]]*(.*)$/\1/')
        if [ -n "$category" ]; then
            echo "$category"
        else
            echo "Uncategorized"
        fi
    fi
}

# ==================================================================================
# Function to get script sub-category from filename prefix
get_subcategory() {
    script="$1"
    basename=$(basename "$script")
    
    # Handle subdirectories
    if [[ "$script" == */service/* ]]; then
        echo "service"
    elif [[ "$script" == */extras/* ]]; then
        echo "extras"
    # Extract prefix before first underscore
    elif [[ "$basename" =~ ^([a-z]+)_ ]]; then
        echo "${BASH_REMATCH[1]}"
    else
        echo "other"
    fi
}

# ==================================================================================
# Function to explain script purpose
explain_purpose() {
    script="$1"
    if [ -f "$script" ]; then
        # Match both '# purpose:' and '#  purpose:'
        purpose_function=$(grep -m 1 -E "^[[:space:]]*# ? ?purpose:.*" "$script" | sed -E 's/^[[:space:]]*# ? ?purpose:[[:space:]]*(.*)$/\1/')
        if [ -n "$purpose_function" ]; then
            echo "$purpose_function"
        else
            echo "No purpose information found."
        fi
    fi
}

# ==================================================================================
# Function to get script parameters (if any)
get_parameters() {
    script="$1"
    if [ -f "$script" ]; then
        # Match both '# parameters:' and '#  parameters:'
        parameters=$(grep -m 1 -E "^[[:space:]]*# ? ?parameters:.*" "$script" | sed -E 's/^[[:space:]]*# ? ?parameters:[[:space:]]*(.*)$/\1/')
        echo "$parameters"
    fi
}

# ==================================================================================
# Function to display sub-category menu
display_subcategory_menu() {
    # Declare as global associative array to avoid unbound variable error
    declare -gA subcategory_counts
    subcategory_counts=()

    # Count scripts in each subcategory
    for script in "${filtered_scripts[@]}"; do
        subcat=$(get_subcategory "$script")
        subcategory_counts["$subcat"]=$(( ${subcategory_counts["$subcat"]:-0} + 1 ))
    done

    # Display menu
    echo -e "${BYellow}Select a script category:${Color_Off}"
    echo ""
    unique_number=1
    for subcat in $(echo "${!subcategory_counts[@]}" | tr ' ' '\n' | sort); do
        count=${subcategory_counts[$subcat]}
        # Convert subcategory name to display format
        display_name=""
        case "$subcat" in
            ble) display_name="Bluetooth Configuration" ;;
            dev) display_name="Development Tools" ;;
            diag) display_name="Diagnostics" ;;
            env) display_name="Environment Setup" ;;
            sys) display_name="System Setup" ;;
            test) display_name="Testing" ;;
            usb) display_name="USB/MTP" ;;
            service) display_name="Service Management" ;;
            extras) display_name="BLE Extras" ;;
            other) display_name="Other Scripts" ;;
            *) display_name="$subcat" ;;
        esac
        printf "  %-5s %-40s (%d scripts)\n" "[$unique_number]:" "$display_name" "$count"
        subcategory_mapping["$unique_number"]="$subcat"
        ((unique_number++))
    done
    
    echo ""
    echo -e "${BYellow}Program functions:${Color_Off}"
    echo "  [0]: Exit"
}

# ==================================================================================
# Function to display scripts in selected subcategory
display_scripts_menu() {
    local selected_subcat="$1"
    
    declare -A script_list
    
    # Filter scripts by subcategory
    for script in "${filtered_scripts[@]}"; do
        subcat=$(get_subcategory "$script")
        if [ "$subcat" == "$selected_subcat" ]; then
            script_list["$script"]=1
        fi
    done

    # Display menu
    local display_name=""
    case "$selected_subcat" in
        ble) display_name="Bluetooth Configuration" ;;
        dev) display_name="Development Tools" ;;
        diag) display_name="Diagnostics" ;;
        env) display_name="Environment Setup" ;;
        sys) display_name="System Setup" ;;
        test) display_name="Testing" ;;
        usb) display_name="USB/MTP" ;;
        service) display_name="Service Management" ;;
        extras) display_name="BLE Extras" ;;
        other) display_name="Other Scripts" ;;
        *) display_name="$selected_subcat" ;;
    esac
    
    echo -e "${BYellow}$display_name Scripts:${Color_Off}"
    echo -e "${BYellow}$(repeat ${#display_name} "-")${Color_Off}"
    
    unique_number=1
    # Sort script_list keys robustly and handle spaces in filenames
    while IFS= read -r script; do
        script_purpose=$(explain_purpose "$script")
        if [ -z "$script_purpose" ]; then
            script_purpose="No purpose information found."
        fi
        printf "  %-5s %-40s - %s\n" "[$unique_number]:" "$(basename "$script")" "$script_purpose"
        script_number_mapping["$unique_number"]="$script"
        ((unique_number++))
    done < <(printf '%s\n' "${!script_list[@]}" | sort)
    
    echo ""
    echo -e "${BYellow}Navigation:${Color_Off}"
    echo "  [b]: Back to category menu"
    echo "  [0]: Exit"
}

#
# Parse optional parameters
#
categories=()
scripts_to_exclude=()
while getopts ":c:e:" opt; do
    case ${opt} in
        c )
            IFS=',' read -ra categories <<< "${OPTARG}"
            categories=("${categories[@],,}") # Convert categories to lowercase
            ;;
        e )
            IFS=',' read -ra scripts_to_exclude <<< "${OPTARG}"
            ;;
        \? )
            echo "Invalid option: $OPTARG" 1>&2
            exit 1
            ;;
        : )
            echo "Invalid option: $OPTARG requires an argument" 1>&2
            exit 1
            ;;
    esac
done
shift $((OPTIND -1))

#
# Array to store script names
#
scripts=()

#
# Find all executable scripts in the scripts directory and subdirectories
#
cd "$SCRIPT_DIR"
while IFS= read -r -d '' script; do
    if [[ $script == *.sh ]] || [[ -x $script ]]; then
        # Skip non-script files
        if [[ $script == *.txt ]] || [[ $script == *.ini ]] || [[ $script == *.toml ]] || [[ $script == *.md ]] || [[ $script == LICENSE ]]; then
            continue
        fi
        # Skip self
        if [[ $(basename "$script") == "scmd.sh" ]]; then
            continue
        fi
        scripts+=("$script")
    fi
done < <(find . -type f \( -name "*.sh" -o -name "*.py" \) ! -path "./.git*" ! -path "./.vscode/*" ! -path "./tmp/*" -print0)

#
# Excluded scripts (if any specific ones need to be skipped)
#
excluded_scripts=()

#
# Create a new array without the excluded scripts
#
filtered_scripts=()
for script in "${scripts[@]}"; do
    if [[ ! " ${excluded_scripts[@]} " =~ " $script " ]] &&
       [[ ! " ${scripts_to_exclude[@]} " =~ " $script " ]]; then
        filtered_scripts+=("$script")
    fi
done


# Mappings for menu navigation (declare as global associative arrays)
declare -gA subcategory_mapping
declare -gA script_number_mapping

#
# Main menu loop
#
while true; do
    clear
    echo -e "${BGreen}=== IPR-Keyboard Script Command Menu ===${Color_Off}"
    echo ""
    display_subcategory_menu

    echo ""
    echo -n -e "${BYellow}Enter the category number (0 to exit): ${Color_Off}"
    read category_choice

    # Check user input
    if is_valid_number "$category_choice"; then
        if [ "$category_choice" -eq 0 ]; then
            echo -e "${BGreen}Exiting.${Color_Off}"
            break
        elif [ -n "${subcategory_mapping[$category_choice]}" ]; then
            selected_subcat="${subcategory_mapping[$category_choice]}"
            
            # Script selection loop for this subcategory
            while true; do
                clear
                echo -e "${BGreen}=== IPR-Keyboard Script Command Menu (${selected_subcat}) ===${Color_Off}"
                echo ""
                # Clear global script_number_mapping before repopulating
                script_number_mapping=()
                display_scripts_menu "$selected_subcat"

                echo ""
                echo -n -e "${BYellow}Enter script number, 'b' for back, or 0 to exit: ${Color_Off}"
                read script_choice

                # Handle navigation
                if [[ "$script_choice" == "b" ]] || [[ "$script_choice" == "B" ]]; then
                    break
                elif [[ "$script_choice" == "0" ]]; then
                    echo -e "${BGreen}Exiting.${Color_Off}"
                    exit 0
                elif is_valid_number "$script_choice" && [ -n "${script_number_mapping[$script_choice]}" ]; then
                    selected_script="${script_number_mapping[$script_choice]}"
                    # Always use absolute path for chmod and execution
                    script_path="$selected_script"
                    if [[ "$script_path" != /* ]]; then
                        script_path="$SCRIPT_DIR/${script_path#./}"
                    fi
                    chmod +x "$script_path"

                    echo -e "${BBlue}$(repeat 80 "=")${Color_Off}"
                    echo -e "${BGreen}Selected script: $script_path${Color_Off}"

                    # Determine if the selected script has parameters
                    script_params=$(get_parameters "$script_path")
                    params=""
                    if [ -n "$script_params" ]; then
                        IFS=',' read -r -a param_array <<< "$script_params"
                        # Display parameters
                        echo -e "${BYellow}Possible parameters:${Color_Off}"
                        for index in "${!param_array[@]}"; do
                            echo -e "${BYellow}  $((index+1)). ${param_array[index]}${Color_Off}"
                        done
                        echo ""
                        # Ask for parameters
                        echo -n -e "${BYellow}Enter parameters (if any): ${Color_Off}"
                        read params_input

                        # Process selected parameters
                        params_array=()
                        IFS=" " read -r -a param_input_array <<< "$params_input"
                        for param_input in "${param_input_array[@]}"; do
                            if [[ "$param_input" =~ ^[0-9]+$ ]]; then
                                index=$((param_input-1))
                                if [ "$index" -ge 0 ] && [ "$index" -lt "${#param_array[@]}" ]; then
                                    params_array+=("${param_array[index]}")
                                else
                                    params_array+=("$param_input")
                                fi
                            else
                                params_array+=("$param_input")
                            fi
                        done
                        params="${params_array[@]}"
                    fi

                    # Check for sudo metadata
                    sudo_flag=$(grep -m 1 -E '^[[:space:]]*# ?sudo:[[:space:]]*yes' "$script_path" || true)
                    sudo_prefix=""
                    if [ -n "$sudo_flag" ]; then
                        sudo_prefix="sudo "
                    fi

                    # Execute the selected script
                    cd "$CURRENT_DIR"
                    echo -e "${BGreen}Executing '${sudo_prefix}$script_path' in directory '$CURRENT_DIR'${Color_Off}"
                    echo -e "${BBlue}$(repeat 80 "=")${Color_Off}"
                    if [ -n "$params" ]; then
                        eval "$sudo_prefix\"$script_path\" $params"
                        script_exit_code=$?
                    else
                        eval "$sudo_prefix\"$script_path\""
                        script_exit_code=$?
                    fi
                    # Prevent menu from terminating if the executed script fails
                    set +e
                    echo -e "${BBlue}$(repeat 80 "=")${Color_Off}"
                    if [ $script_exit_code -ne 0 ]; then
                        echo -e "${BRed}Script exited with code $script_exit_code${Color_Off}"
                    fi
                    # Show script purpose after execution for user context
                    script_purpose=$(explain_purpose "$script_path")
                    if [ -n "$script_purpose" ]; then
                        echo -e "${BYellow}Purpose:${Color_Off} $script_purpose"
                    fi
                    echo ""
                    echo -n -e "${BYellow}Press [Enter] to continue...${Color_Off}"
                    read
                    set -e
                else
                    echo -e "${BRed}Invalid choice. Please enter a valid number.${Color_Off}"
                    sleep 2
                fi
            done
        else
            echo -e "${BRed}Invalid choice. Please enter a valid number.${Color_Off}"
            sleep 2
        fi
    else
        echo -e "${BRed}Invalid input. Please enter a valid number.${Color_Off}"
        sleep 2
    fi
done

echo -e "${BGreen}Script execution completed${Color_Off}"
