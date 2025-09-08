#!/usr/bin/env python3

import prisma_sase
import argparse
import logging
import os
import sys
import csv

# --- Script Configuration ---
SCRIPT_NAME = 'SASE: Element Prefix List Manager'
SCRIPT_VERSION = "v1.7"

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(SCRIPT_NAME)

# --- Attempt to import Prisma SASE credentials ---
try:
    sys.path.append(os.getcwd())
    from prismasase_settings import PRISMASASE_CLIENT_ID, PRISMASASE_CLIENT_SECRET, PRISMASASE_TSG_ID
except ImportError:
    logger.error("ERROR: prismasase_settings.py not found or variables not set.")
    PRISMASASE_CLIENT_ID = None
    PRISMASASE_CLIENT_SECRET = None
    PRISMASASE_TSG_ID = None


def apply_prefixlist_to_element(sase_session, site_id, element_id, element_name, prefixlist_name, prefix_entries):
    """
    Creates or updates a routing_prefixlist on a single element.
    """
    logger.info(f"  -> Checking element '{element_name}' for prefix list '{prefixlist_name}'...")
    
    # 1. Get all existing prefix lists on this specific element
    existing_prefixlists_on_element = {}
    try:
        resp = sase_session.get.routing_prefixlists(site_id=site_id, element_id=element_id)
        if resp.ok:
            for pl in resp.json().get('items', []):
                existing_prefixlists_on_element[pl['name']] = pl
        else:
            logger.error(f"    - FAILURE: Could not get prefix lists for element '{element_name}'. Status: {resp.status_code}, Info: {resp.text}")
            return
    except Exception as e:
        logger.error(f"    - EXCEPTION: An error occurred while getting prefix lists for element '{element_name}': {e}")
        return

    # 2. Prepare the list of prefix entries
    prefix_filter_list_entries = []
    for i, entry_data in enumerate(prefix_entries):
        prefix_str = entry_data.get('prefix')
        ge_val_str = entry_data.get('ge', '0')
        le_val_str = entry_data.get('le', '0')

        try:
            ge_val = int(ge_val_str) if ge_val_str else 0
        except (ValueError, TypeError):
            ge_val = 0
        try:
            le_val = int(le_val_str) if le_val_str else 0
        except (ValueError, TypeError):
            le_val = 0

        entry = {
            "order": (i + 1) * 10,
            "permit": True,
            "prefix": prefix_str,
            "ipv6_prefix": None,
            "ge": ge_val,
            "le": le_val
        }
        prefix_filter_list_entries.append(entry)
    
    # 3. Check if our target prefix list exists on this element
    if prefixlist_name in existing_prefixlists_on_element:
        # It exists, so we will update it using PUT
        existing_pl = existing_prefixlists_on_element[prefixlist_name]
        prefixlist_id = existing_pl['id']
        
        # Use the existing object as the base for the payload to preserve _etag
        payload = existing_pl.copy()
        
        # Update the fields we want to change
        payload['description'] = f"Prefix list '{prefixlist_name}'. Managed by script."
        payload['prefix_filter_list'] = prefix_filter_list_entries
        
        logger.info(f"    - Prefix list '{prefixlist_name}' exists. Updating...")
        try:
            resp = sase_session.put.routing_prefixlists(site_id=site_id, element_id=element_id, routing_prefixlist_id=prefixlist_id, data=payload)
            if resp.ok:
                logger.info(f"    - SUCCESS: Updated prefix list on '{element_name}'.")
            else:
                logger.error(f"    - FAILURE: Could not update prefix list on '{element_name}'. Status: {resp.status_code}, Info: {resp.text}")
        except Exception as e:
            logger.error(f"    - EXCEPTION: An error occurred while updating prefix list on '{element_name}': {e}")
    else:
        # It does not exist, so we will create it using POST
        payload = {
            "name": prefixlist_name,
            "description": f"Prefix list '{prefixlist_name}'. Managed by script.",
            "tags": None,
            "auto_generated": False,
            "prefix_filter_list": prefix_filter_list_entries
        }
        logger.info(f"    - Prefix list '{prefixlist_name}' does not exist. Creating...")
        try:
            resp = sase_session.post.routing_prefixlists(site_id=site_id, element_id=element_id, data=payload)
            if resp.ok:
                logger.info(f"    - SUCCESS: Created prefix list on '{element_name}'.")
            else:
                logger.error(f"    - FAILURE: Could not create prefix list on '{element_name}'. Status: {resp.status_code}, Info: {resp.text}")
        except Exception as e:
            logger.error(f"    - EXCEPTION: An error occurred while creating prefix list on '{element_name}': {e}")


def go():
    """
    Main execution function.
    """
    parser = argparse.ArgumentParser(description=f"{SCRIPT_NAME} - {SCRIPT_VERSION}")
    parser.add_argument("csv_filepath", help="Path to the input CSV file containing site and prefix information.")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        for handler in logging.getLogger().handlers:
            handler.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled.")

    if not all([PRISMASASE_CLIENT_ID, PRISMASASE_CLIENT_SECRET, PRISMASASE_TSG_ID]):
        logger.error("Prisma SASE API credentials not configured.")
        sys.exit(1)

    sase_session = prisma_sase.API()
    sase_session.set_debug(2 if args.debug else 0)
    
    logger.info("Attempting to log in...")
    if not sase_session.interactive.login_secret(client_id=PRISMASASE_CLIENT_ID, client_secret=PRISMASASE_CLIENT_SECRET, tsg_id=PRISMASASE_TSG_ID):
        logger.error("Login failed. Please check credentials.")
        sys.exit(1)
    
    logger.info(f"Successfully logged in. Tenant ID: {sase_session.tenant_id}")
    
    # Pre-fetch all sites and elements for efficiency
    logger.info("Fetching all sites and elements...")
    all_sites_map = {}
    all_elements = []
    try:
        sites_resp = sase_session.get.sites()
        elements_resp = sase_session.get.elements()
        if not sites_resp.ok or not elements_resp.ok:
            logger.error("Failed to pre-fetch sites or elements. Exiting.")
            sys.exit(1)
            
        for site in sites_resp.json().get('items', []):
            all_sites_map[site['name']] = site
        all_elements = elements_resp.json().get('items', [])
        logger.info(f"Found {len(all_sites_map)} sites and {len(all_elements)} elements.")
    except Exception as e:
        logger.error(f"An error occurred during pre-fetch: {e}")
        sys.exit(1)

    # Process the input CSV file
    try:
        grouped_tasks = {}
        last_target_sites = ""
        last_prefixlist_name = ""
        
        with open(args.csv_filepath, mode='r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            required_headers = ['target_sites', 'prefixlist_name', 'prefixes']
            if not all(h in reader.fieldnames for h in required_headers):
                logger.error(f"Input CSV must contain headers: {', '.join(required_headers)}.")
                sys.exit(1)
                
            for row in reader:
                # Carry forward target sites and prefixlist name from previous rows if blank
                current_target_sites = row.get('target_sites', '').strip()
                if current_target_sites:
                    last_target_sites = current_target_sites
                
                current_prefixlist_name = row.get('prefixlist_name', '').strip()
                if current_prefixlist_name:
                    last_prefixlist_name = current_prefixlist_name
                
                prefixes_str = row.get('prefixes', '').strip()
                ge_val = row.get('ge', '').strip()
                le_val = row.get('le', '').strip()

                if not prefixes_str:
                    logger.warning(f"Skipping row with no prefixes defined: {row}")
                    continue

                if not last_target_sites or not last_prefixlist_name:
                    logger.warning(f"Skipping row because target sites or prefixlist name is not yet defined: {row}")
                    continue
                
                # Create a key to group prefixes by site and list name
                group_key = (last_target_sites, last_prefixlist_name)
                if group_key not in grouped_tasks:
                    grouped_tasks[group_key] = []
                
                # Handle potentially multiple comma-separated prefixes in a single cell
                for prefix in [p.strip() for p in prefixes_str.split(',') if p.strip()]:
                    grouped_tasks[group_key].append({
                        "prefix": prefix,
                        "ge": ge_val,
                        "le": le_val
                    })

        # Once the entire CSV is read and grouped, process the tasks
        for (target_sites_str, prefixlist_name), prefix_entries in grouped_tasks.items():
            target_site_names = [s.strip() for s in target_sites_str.split(',') if s.strip()]

            for site_name in target_site_names:
                logger.info(f"\n--- Applying prefix list '{prefixlist_name}' to site: {site_name} ---")

                if site_name not in all_sites_map:
                    logger.warning(f"Target site '{site_name}' from CSV not found in tenant. Skipping.")
                    continue
                
                site_id = all_sites_map[site_name]['id']
                elements_at_site = [elem for elem in all_elements if elem.get('site_id') == site_id]

                if not elements_at_site:
                    logger.info(f"No elements found at site '{site_name}'.")
                    continue

                # Apply the full list of grouped prefixes to every element at this site
                for element in elements_at_site:
                    apply_prefixlist_to_element(sase_session, site_id, element['id'], element['name'], prefixlist_name, prefix_entries)

    except FileNotFoundError:
        logger.error(f"Input CSV file not found: {args.csv_filepath}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An error occurred while processing CSV: {e}")
        sys.exit(1)

if __name__ == "__main__":
    logger.info(f"Starting {SCRIPT_NAME} v{SCRIPT_VERSION}")
    go()
    logger.info(f"\nFinished {SCRIPT_NAME}.")

