from recom import generate_tree_care_json
from geopy.geocoders import Nominatim

zipCode = input("what is your zip code?")
species = "spruce"

geolocator = Nominatim(user_agent="my_geocoder")
location = geolocator.geocode(zipCode) # Replace with your zip code
userLat = location.latitude
userLong = location.longitude
print(userLat, userLong)


# info = generate_tree_care_json(
#     species_name=species,
#     latitude=userLat,
#     longitude=-userLong,
#     output_file_path=f"output/{species}Care.json"
# )
# print(info)