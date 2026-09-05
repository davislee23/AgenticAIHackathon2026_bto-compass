import json
import requests

url = "https://onemap.gov.sg"
headers = {"Authorization": "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoyMjY0NywiZm9yZXZlciI6ZmFsc2UsImlzcyI6Ik9uZU1hcCIsImlhdCI6MTc4ODU4NzYzNiwibmJmIjoxNzg4NTg3NjM2LCJleHAiOjE3ODg4NDY4MzYsImp0aSI6Ijg0MTRmYmExLWU1ZWMtNDIwYS1hMDBjLTY2MmVjNWFjMThjYiJ9.mbRdsDCpY0dp2WrFRbyQtcVq8Hi6A43azN2kbOZJt1MexWyPDvQl1Vz1HFSAOyxo74sPNG3OFjbzv5P_FwtnLNxHL4KDH2yPmPW8NEcXM27o4z41lcUwQ6potDERxTQm3TJn6tnvgTp2CFP3gUhqavmUtb6UIg8TiQ_GJwd8v9_4_lVyXI2kvecG4SZjgz1ZerfzsNKSPs9kNIC3U5AABY7xgG2AF0QodNqObzIE5UHoKUp18vXZhWwSrih5d01bIhzZ1qlHtZeJb2Lihjs09MR1ahWPoOxlfZU2xzajUJ0x7BQF4riVuBVLUmmH-aNYmP7DKPoKbFvymdujQZjYCw"}

response = requests.get(url, headers=headers)
data = response.json()

with open("output.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

