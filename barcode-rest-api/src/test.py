#!/usr/bin/env python3

import pycurl
import json
from io import BytesIO

url = "http://scanqr.azurewebsites.net/save"
data = json.dumps({
    "id": "23456456735",
    "name": "Prodware"
}).encode('utf-8')

buffer = BytesIO()

c = pycurl.Curl()
c.setopt(c.URL, url)
c.setopt(c.WRITEDATA, buffer)
c.setopt(c.CUSTOMREQUEST, "POST")
c.setopt(c.HTTPHEADER, ["Content-Type: application/json"])
c.setopt(c.POSTFIELDS, data.decode('utf-8'))

c.perform()
c.close()

response = buffer.getvalue().decode('utf-8')
print("Response:", response)