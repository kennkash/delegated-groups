## How can I add another element to the scheduled script below while keeping its current functionality intact? I want to basically sync the delegated groups DB with the Confluence and Jira groups that are pulled/found here. 

## If a group exists in my postgreSQL DB but does not exist in this pull, I want to delete it from the DB. I want to do this because if not, I will be displaying groups that no longer exists in Jira or Confluence. 


# atlassian-db/db-main.py
from sas_auth_wrapper import get_external_api_session
import models
from models import SessionLocal
from bigdataloader2 import getData
import json
from io import BytesIO
from s2cloudapi import s3api as s3
import pandas as pd

external_api_session = get_external_api_session()
session = SessionLocal()
#--------------------------------AUTH--------------------------------#
def read_json_from_bucket(bucket: str, key: str) -> dict:
    """Read a .json file from an s3 bucket as a dictionary
 
    Args:
        bucket (str): name of bucket
        key (str): filepath ending in .json
 
    Returns:
        dict: file as dict
    """
    boto_object = s3.get_object(bucket=bucket, key=key)
    # read in body as bytes to memory
    datafile = BytesIO(boto_object["Body"].read())

    return json.load(datafile)

def getCreds(bot: str) -> json:
    bucket = "atlassian-bucket"
    key = "passwords.json"
    # read password in
    bot_creds = read_json_from_bucket(bucket=bucket, key=key)

    bot_password = bot_creds[bot]

    return bot_password

#--------------------------------GROUPS--------------------------------#
# Creates the tables confluenceGroups & jiraGroups in postgreSQL

# Gets all Confluence/Jira group owners from delegated groups REST API
def get_delegated_groups(app):
    delegated_groups = []
    app = app
    if app == "confluence":
        column='conf'
        base_url = "http://confluence.externalapi.smartcloud.samsungaustin.com/rest/"
    else:
        column='jira'
        base_url = "http://jira.externalapi.smartcloud.samsungaustin.com/rest/"

    bot_password =  getCreds(app)
    auth_token = bot_password
    header = {"Authorization": f"Bearer {auth_token}"}

    api_path = f"{base_url}wittified/delegated-groups/1.0/delegation/getAll"
    r = external_api_session.get(api_path, headers=header)
    json_string = r.json()


    for group_data in json_string:
        delegated_groups.append(group_data["group"])


    delegated_groups_dict = {group_data["group"].lower(): group_data["group"] for group_data in json_string}
    
    df = pd.DataFrame(list(delegated_groups_dict.items()), columns=['group_lowercase', f'{column}_group'])

    df = df[[f'{column}_group', 'group_lowercase']]

    return df
# Gets all Confluence/Jira groups & the member count from scriptrunner
def group_count(app):
    app = app

    if app == "confluence":
        column='conf'
        base_url = "http://confluence.externalapi.smartcloud.samsungaustin.com/rest/"
    else:
        column='jira'
        base_url = "http://jira.externalapi.smartcloud.samsungaustin.com/rest/"

    bot_password = getCreds(app)
    auth_token = bot_password
    header = {"Authorization": f"Bearer {auth_token}"}

    api_path = f"{base_url}scriptrunner/latest/custom/getAllGroupsWithUserCount"
    t = external_api_session.get(api_path, headers=header)
    response_json = t.json()

    filtered_response = [
        item for item in response_json
        if not (
            item["name"].lower().startswith("fse") or
            item["name"].lower().startswith("bc_") or
            item["name"].lower().startswith("citrix") or
            item["name"].lower().startswith("cyberark") or
            item["name"].lower().startswith("dcm") or
            item["name"].lower().startswith("xd_") or
            item["name"].lower().startswith("$") or
            item["name"].lower().startswith("file-share") or
            item["name"].lower().startswith("app_") or
            item["name"].lower().startswith("a2") or
            item["name"].lower().startswith("xd_") or
            item["name"].lower().startswith("org1") or
            item["name"].lower().startswith("org2") or
            item["name"].lower().startswith("orgc1") or
            item["name"].lower().startswith("orgd") or
            item["name"].lower().startswith("orgk") or
            item["name"].lower().startswith("orgsa") or
            item["name"].lower().startswith("orgt") or
            item["name"].lower().startswith("bluecoat") or 
            item["name"].lower().startswith("aria_") or 
            item["name"].lower().startswith("dc2x") or 
            item["name"].lower().startswith("di-") or 
            item["name"].lower().startswith("di_") or 
            item["name"].lower().startswith("ds-") or 
            item["name"].lower().startswith("dscloud_") or 
            item["name"].lower().startswith("edm_") or 
            item["name"].lower().startswith("mecmagent") or 
            item["name"].lower().startswith("opls-") or 
            item["name"].lower().startswith("prtg-") or 
            item["name"].lower().startswith("reviews_") or 
            item["name"].lower().startswith("s2_vmware") or 
            item["name"].lower().startswith("t1_vmware-") or 
            item["name"].lower().startswith("sp") or 
            item["name"].lower().startswith("sg") or 
            item["name"].lower().startswith("wg")
        )
    ]
    df = pd.DataFrame(filtered_response)
    # Rename the 'name' column to 'conf_groups'
    df.rename(columns={'name': f'{column}_group'}, inplace=True)
    return df


    # file_name='ldap-groups'

    # if s3.chk_file_exist('atlassian-bucket', file_name):
    #     ldap_groups = pickle.loads(s3.get_object('atlassian-bucket', file_name)['Body'].read())
    #     # Extract the "AD Groups" column and convert it to a set
    #     ad_groups_set = set(ldap_groups['AD groups'])

    #     # Filter out groups in response_json that are in ad_groups_set
    #     filtered_groups = [group for group in response_json if group['name'] not in ad_groups_set]
    #     df = pd.DataFrame(filtered_groups)
    #     # Rename the 'name' column to 'conf_groups'
    #     df.rename(columns={'name': f'{column}_group'}, inplace=True)
    #     return df
    # else:
    #     # If ldap_groups file does not exist, return the original response_json
    #     df = pd.DataFrame(response_json)
    #     return df

# Gets all Confluence/Jira groups & their member count/owners from scriptrunner & REST API
def get_groups(app):
    app = app
    if app == "confluence":
        column='conf'
    else:
        column='jira'
    delegated = get_delegated_groups(app)
    groups = group_count(app)

    merged_df = pd.merge(groups, delegated, left_on=f'{column}_group', right_on='group_lowercase', how='left')

    # Create the 'delegated' column with boolean values
    merged_df['delegated'] = merged_df[f'{column}_group_y'].notna()

    # Create the 'del_group' column
    merged_df['del_group'] = merged_df[f'{column}_group_y']

    # Drop the unnecessary columns
    merged_df.drop(columns=['group_lowercase', f'{column}_group_y'], inplace=True)
    # Rename f'{column}_group_x' back to name'
    merged_df.rename(columns={f'{column}_group_x': 'name'}, inplace=True)

    rows_added, new_count, update_count, delete_count = add_data_to_table(merged_df, app)
    print(rows_added)
    print(f'new rows added to {app}Groups: ', new_count)
    print(f'updated rows in {app}Groups: ', update_count)
    print(f'deleted rows in {app}Groups: ', delete_count)


# Adds Confluence/Jira group data to postgreSQL
def add_data_to_table(df, app):
    if app == 'confluence':
        table = models.confluenceGroups
    else:
        table = models.jiraGroups

    final_df = df
    # Get the list of existing groups in the confluenceGroups table
    existing_groups = [row.name for row in session.query(
        table.name).distinct()]

    event_counter_update = 0
    event_counter_new = 0
    event_counter_delete = 0

    for index, row in final_df.iterrows():
        name = row['name']
        if name in existing_groups:
            # Update the existing row
            existing_row = session.query(
                table).filter_by(name=name).first()
            for key, value in row.items():
                setattr(existing_row, key, value)
            session.commit()
            event_counter_update += 1
        else:
            # Insert a new row
            row_val = table(**row)
            session.add(row_val)
            session.commit()
            event_counter_new += 1

    # Delete the rows that are no longer present in the final_df
    rows_to_delete = session.query(table).filter(
        table.name.not_in(final_df['name']))

    # Capture the names of the rows to delete
    deleted_names = [row.name for row in rows_to_delete]

    # Print the names of the rows being deleted only if there are rows to delete
    if deleted_names:
        print(f"Rows to be deleted: {deleted_names}")
    
    for row in rows_to_delete:
        session.delete(row)
        event_counter_delete += 1
    session.commit()
    session.close()
    return final_df, event_counter_new, event_counter_update, event_counter_delete

#--------------------------------USERS--------------------------------#
# Creates the tables confluenceUsers & jiraUsers in postgreSQL

# Gets all users to filter out
def restricted_users():
    params = {'data_type': 'pageradm_employee_ghr',
            'MLR': 'L',
            'title': ['SVP', 'VP', 'EVP', 'Director', 'Senior Director'],
            'status_name': 'Active'}
    custom_columns = ['nt_id']
    custom_operators = {'nt_id': 'notnull'}
    data = getData(params=params, custom_columns=custom_columns, custom_operators=custom_operators)
    return data



# Gets all Confluence users from REST API
def get_conf_users():
    app = "confluence"
    bot_password = getCreds(app)
    auth_token = bot_password
    header = {"Authorization": f"Bearer {auth_token}"}

    base_url = "http://confluence.externalapi.smartcloud.samsungaustin.com/rest/"
    limit = 200
    start = 0
    usernames = []
    while True:
        api_path = f"{base_url}api/user/list?start={start}&limit={limit}"
        v = external_api_session.get(api_path, headers=header)
        response_json = v.json()

        for result in response_json["results"]:
            profile_picture_path = result.get("profilePicture", {}).get("path", "")
            profile_picture_id = None
            if profile_picture_path.startswith("/download/attachments/"):
                components = profile_picture_path.split("/")
                if len(components) >= 4 and components[2] == "attachments":
                    profile_picture_id = components[3]
            elif profile_picture_path == "/images/icons/profilepics/default.svg":
                profile_picture_id = "default"

            usernames.append(
                {
                    "username": result["username"],
                    "displayName": result["displayName"],
                    "profilePictureId": profile_picture_id,
                }
            )
        if len(response_json["results"]) < limit:
            break

        start += limit
    user_df = pd.DataFrame(usernames)

    # restricted = restricted_users()
    # restricted['nt_id'] = restricted['nt_id'].str.lower()
    # restricted_usernames = restricted['nt_id'].tolist()

    # Step 3: Filter df to exclude restricted usernames
    # user_df = df[~df['username'].isin(restricted_usernames)]

    rows_added, new_count, update_count, delete_count = add_user_data(user_df, app)
    print(rows_added)
    print(f'new rows added to {app}Users: ', new_count)
    print(f'updated rows in {app}Users: ', update_count)
    print(f'deleted rows in {app}Users: ', delete_count)

# Gets all Jira users from REST API
def get_jira_users():
    app = "jira"
    bot_password = getCreds(app)
    auth_token = bot_password
    header = {"Authorization": f"Bearer {auth_token}"}

    base_url = "http://jira.externalapi.smartcloud.samsungaustin.com/rest/"
    limit = 1000
    start = 0
    users = []
    api_path = f"{base_url}api/2/user/search?username=."

    while True:
        api_path_with_params = f"{api_path}&maxResults={limit}&startAt={start}"
        r = external_api_session.get(api_path_with_params, headers=header)
        response_json = r.json()

        for result in response_json:
            profile_picture_path = result["avatarUrls"]["48x48"]
            if "useravatar?" in profile_picture_path:
                path = profile_picture_path.split("useravatar?")[1]
            else:
                path = profile_picture_path

            users.append(
                {
                    "username": result["name"],
                    "displayName": result["displayName"],
                    "profilePictureId": path,
                }
            )

        if len(response_json) < limit:
            break

        start += limit
    
    user_df = pd.DataFrame(users)

    # restricted = restricted_users()
    # restricted['nt_id'] = restricted['nt_id'].str.lower()
    # restricted_usernames = restricted['nt_id'].tolist()

    # Step 3: Filter df to exclude restricted usernames
    # user_df = df[~df['username'].isin(restricted_usernames)]

    rows_added, new_count, update_count, delete_count = add_user_data(user_df, app)
    print(rows_added)
    print(f'new rows added to {app}Users: ', new_count)
    print(f'updated rows in {app}Users: ', update_count)
    print(f'deleted rows in {app}Users: ', delete_count)


# Adds Confluence/Jira user data to postgreSQL
def add_user_data(df, app):
    if app == 'confluence':
        table = models.confluenceUsers
    else:
        table = models.jiraUsers

    final_df = df.drop_duplicates(subset='username')  # Remove duplicate usernames

    event_counter_update = 0
    event_counter_new = 0
    event_counter_delete = 0

    try:
        session.begin()

        # Convert DataFrame to list of dictionaries for easier processing
        new_users = final_df.to_dict(orient='records')

        # Prepare a set of usernames from the DataFrame for quick lookup
        new_usernames = set(user['username'] for user in new_users)

        # Fetch existing usernames to compare
        existing_usernames = {row.username for row in session.query(table.username).distinct()}

        # Prepare list to store inserts and updates
        inserts = []
        updates = []

        for user in new_users:
            username = user['username']
            if username in existing_usernames:
                # Prepare update
                updates.append(user)
            else:
                # Prepare insert
                inserts.append(user)

        # Perform updates
        for user in updates:
            existing_row = session.query(table).filter_by(username=user['username']).first()
            for key, value in user.items():
                setattr(existing_row, key, value)
            event_counter_update += 1

        # Perform inserts
        if inserts:
            session.add_all([table(**user) for user in inserts])
            event_counter_new = len(inserts)

        # Delete the rows that are no longer present in the final_df
        rows_to_delete = session.query(table).filter(
            table.username.not_in(new_usernames))
        if rows_to_delete.count() > 0:
            deleted_usernames = [row.username for row in rows_to_delete]
            print(f"Deleting users: {deleted_usernames}")
        for row in rows_to_delete:
            session.delete(row)
            event_counter_delete += 1

        # Commit the transaction
        session.commit()

    except Exception as e:
        # Rollback in case of error
        session.rollback()
        print(f"An error occurred: {e}")
        raise  # Re-raise the exception after logging
    finally:
        session.close()
    return final_df, event_counter_new, event_counter_update, event_counter_delete



#--------------------------------Run main()--------------------------------#
# Running all functions to populate 4 postgreSQL tables (confluenceGroups, jiraGroups, confluenceUsers, jiraUsers)
jira = 'jira'
conf='confluence'
def main():
    try:
        print("Starting Confluence groups...")
        get_groups(conf)
        print("Confluence groups completed successfully.")
        
        print("Starting Jira groups...")
        get_groups(jira) 
        print("Jira groups completed successfully.")
        
        print("Starting Confluence users...")
        get_conf_users()
        print("Confluence users completed successfully.")
        
        print("Starting Jira users...")
        get_jira_users()
        print("Jira users completed successfully.")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        raise

if __name__ == "__main__":
    main()



# atlassian-db/models.py
import sqlalchemy as db
import json
from io import BytesIO
from s2cloudapi import s3api as s3
from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

def read_json_from_bucket(bucket: str, key: str) -> dict:
    """Read a .json file from an s3 bucket as a dictionary
 
    Args:
        bucket (str): name of bucket
        key (str): filepath ending in .json
 
    Returns:
        dict: file as dict
    """
    boto_object = s3.get_object(bucket=bucket, key=key)
    # read in body as bytes to memory
    datafile = BytesIO(boto_object["Body"].read())

    return json.load(datafile)

def getCreds(bot: str) -> json:
    bucket = "atlassian-bucket"
    key = "passwords.json"
    # read password in
    bot_creds = read_json_from_bucket(bucket=bucket, key=key)

    bot_password = bot_creds[bot]

    return bot_password


# # creating connection to postegresql db
# app = "psql"
# password = getCreds(app)
# db_name = "AtlassianCloud"
# user = 'atlassian-bot'
# schema = 'atlassian-admin'
app = "psql-dev"
password = getCreds(app)
db_name = "AtlassianCloud"
user = "atlassian-bot.dev"
schema = "atlassian-admin.dev"


engine = create_engine(
    f'postgresql+psycopg2://{user}:{password}@psqldb-k-kashmiryclust-kkashmiry0641.dbuser:5432/{db_name}')
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base(metadata=MetaData(schema=schema))



# Confluence Groups Table
class confluenceGroups(Base):
    __tablename__ = 'confluenceGroups'
    name = db.Column(db.String(), primary_key=True)
    userCount = db.Column(db.Integer)
    delegated = db.Column(db.Boolean())
    del_group = db.Column(db.String(), nullable=True)

# Jira Groups Table
class jiraGroups(Base):
    __tablename__ = 'jiraGroups'
    name = db.Column(db.String(), primary_key=True)
    userCount = db.Column(db.Integer)
    delegated = db.Column(db.Boolean())
    del_group = db.Column(db.String(), nullable=True)

# Confluence Users Table
class confluenceUsers(Base):
    __tablename__ = 'confluenceUsers'
    username = db.Column(db.String(), primary_key=True)
    displayName = db.Column(db.String())
    profilePictureId = db.Column(db.String())   

     
# Jira Users Table
class jiraUsers(Base):
    __tablename__ = 'jiraUsers'
    username = db.Column(db.String(), primary_key=True)
    displayName = db.Column(db.String())
    profilePictureId = db.Column(db.String())   



session = SessionLocal()


# following line will create Base classes as tables, if they already exist nothing changes
Base.metadata.create_all(bind=engine)
