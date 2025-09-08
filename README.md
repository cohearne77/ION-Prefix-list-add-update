# SASE Element Prefix List ManagerVersion: 1.7


This Python script automates the creation and updating of routing prefix lists directly on Prisma SASE ION devices. It reads a CSV file to apply multiple, named prefix lists to all devices across one or more specified sites, making bulk configuration simple and repeatable.

### FeaturesBulk Operations: 

Creates or updates prefix lists on all devices at multiple sites from a single CSV file.
* Idempotent: Safely re-running the script will update existing prefix lists with the latest information from the CSV, rather than creating duplicates.
* Complex CSV Logic: Supports grouping multiple prefixes under a single prefix list definition by leaving the target_sites and prefixlist_name columns blank on subsequent lines.
* Flexible Prefix Matching: Allows for optional ge (greater-than-or-equal-to) and le (less-than-or-equal-to) values for more specific prefix matching.

### Prerequisites
* Python 3.6+
* prisma-sase-sdk Python package.
* Prisma SASE API Credentials: You must have a valid Client ID, Client Secret, and TSG ID with permissions to read and write routing prefix list configurations on ION devices.


# Setup
1. Clone the Repository:
  git clone <your-repo-url> cd <your-repo-directory>
2. Install Dependencies:
  A requirements.txt file is included for easy installation of the required Python package.pip install -r requirements.txt
3. Configure API Credentials:Create a file named prismasase_settings.py in the same directory as the script and add your credentials:

> prismasase_settings.py,
>
>PRISMASASE_CLIENT_ID = "your_client_id@services"
>
>PRISMASASE_CLIENT_SECRET = "your_client_secret"
>
>PRISMASASE_TSG_ID = "your_tsg_id"

Alternatively, you can set these as environment variables.

# CSV File Structure
The script requires a CSV file with the headers target_sites, prefixlist_name, prefixes. The headers ge and le are optional.
* target_sites: A comma-separated list of site names where the prefix list will be applied.
* prefixlist_name: The name for the prefix list you are creating or updating.
* prefixes: A comma-separated list of the IP prefixes.
* ge (Optional): The "greater than or equal to" prefix length for a match. Defaults to 0 if blank.
* le (Optional): The "less than or equal to" prefix length for a match. Defaults to 0 if blank.

Continuation Logic
  To add multiple prefixes to the same list without repeating the site and name, leave the target_sites and prefixlist_name columns blank on the following lines. The script will automatically group them.
  
# Example CSV (prefixes_to_apply.csv):
> target_sites,prefixlist_name,prefixes,ge,le
> 
> "EMEA DC,NAM DC",
> SiteA-Allow,"192.168.1.0/24",,
> ,,192.168.2.0/24,,
>,,192.168.3.0/24,,
>
> "EMEA DC,NAM DC",
> SiteB-Block,"172.16.1.0/24",28,32,,172.16.2.0/24,,
>
> NAM DC,SiteC-Specific,"10.100.0.0/16",, 


* This configuration will result in:
  * A prefix list named SiteA-Allow with three prefixes, applied to all devices at EMEA DC and NAM DC.
  * A prefix list named SiteB-Block with two prefixes, also applied to all devices at EMEA DC and NAM DC. The first prefix will have ge=28 and le=32.
  * A prefix list named SiteC-Specific with one prefix, applied only to devices at NAM DC.
  
## Usage
  Run the script from your terminal, providing the path to your CSV file as the main argument. 
  
  `python sase_element_prefix_manager.py prefixes_to_apply.csv`
  
## Debug Mode
  To see verbose output, including the API payloads, use the --debug flag:
  
    `python sase_element_prefix_manager.py prefixes_to_apply.csv --debug`
