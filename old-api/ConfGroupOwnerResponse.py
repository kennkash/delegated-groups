class ConfGroupOwnerResponse(BaseModel):
    userOwners: List[ConfUserOwnerResponse]
    groupOwners: str = Field(..., example="clean admins,cleans_leadership")
    allUserOwners: List[UserOwnerResponse] = Field(..., example=[
        {"username": "icastillo2", "displayName": "Ike Castillo", 'profilePictureId': "11969190"},
        {"username": "spandeti2572", "displayName": "Sramanth Varma Pandeti", 'profilePictureId': "88368665"}, 
        {"username": "janedoe", "displayName": "Jane Doe", 'profilePictureId': "default"},   ])
    group: str = Field(..., example="Cleans")

    class Config:
        populate_by_name = True
