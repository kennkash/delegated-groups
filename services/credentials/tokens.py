# services/v0/credentials/tokens.py
import json
from io import BytesIO
from s2cloudapi import s3api as s3


class AtlassianToken:

    def __init__(self, app):
        """Initializes client with token and creates a Confluence instance."""
        self.__app = app
        self.__bucket = "atlassian-bucket"
        self.__key = "passwords.json"
    def read_json_from_bucket(self) -> dict:
        """Read a .json file from an s3 bucket as a dictionary
    
        Args:
            bucket (str): name of bucket
            key (str): filepath ending in .json
    
        Returns:
            dict: file as dict
        """
        boto_object = s3.get_object(bucket=self.__bucket, key=self.__key)
        # read in body as bytes to memory
        datafile = BytesIO(boto_object["Body"].read())

        return json.load(datafile)

    def getCreds(self) -> json:
        
        # read password in
        bot_creds = self.read_json_from_bucket()

        bot_password = bot_creds.get(self.__app)

        return bot_password
