""" Copyright (c) 2020 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
           https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied. 
"""

# Import Section
import logging
import webbrowser
from flask import Flask, render_template, request, url_for, redirect
from collections import defaultdict
from datetime import datetime
import requests
import json
from dotenv import load_dotenv
import os
from meraki import DashboardAPI
from dnacentersdk import api

# load all environment variables
load_dotenv()


# Global variables
app = Flask(__name__)

#Read data from json file
def getJson(filepath):
	with open(filepath, 'r') as f:
		json_content = json.loads(f.read())
		f.close()

	return json_content

#Write data to json file
def writeJson(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f)
    f.close()


## Routes

#Index
@app.route('/', methods=["GET", "POST"])
def index():
    if request.method == "POST":
        settings = getJson("settings.json")
        networks = dict(request.form.lists())['network']
        n_list = []
        m = DashboardAPI(settings['apikey'])
        for n in networks:
            n_list += [{
                "name" : m.networks.getNetwork(n)['name'],
                "id" : n
            }]
        settings['networks'] = n_list
        writeJson("settings.json", settings)
    
    settings = getJson("settings.json")
    m = DashboardAPI(api_key=settings['apikey'])
    result = []

    # Retrieve wireless clients
    for n in settings['networks']:
        try:
            for c in m.networks.getNetworkClients(n['id'], total_pages='all', perPage=100):
                if c['recentDeviceConnection'] == "Wireless":
                    result += [{
                        'network' : n['name'],
                        'networkid' : n['id'],
                        'id' : c['id'],
                        'user' : c['user'],
                        'name' : c['description'],
                        'lastSeen' : c['lastSeen'],
                        'vendor' : c['manufacturer'],
                        'ap' : c['recentDeviceSerial']
                    }]
        except Exception as e:
            print(e)

    try:
        return render_template('home.html', hiddenLinks=True, clients=result)
    except Exception as e: 
        print(e)  
        return render_template('home.html', hiddenLinks=True)

# Client data
@app.route('/client', methods=["GET"])
def client():
    id = request.args.get("id")
    network = request.args.get("network")
    serial = request.args.get("ap")
    settings = getJson('settings.json')

    m = DashboardAPI(settings['apikey'])

    # Cross-launch Meraki dashboard
    url = f"{m.networks.getNetwork(network)['url']}/overview?t0={datetime.now().timestamp()-86400}&t1={datetime.now().timestamp()}#c={id}"
    webbrowser.open_new_tab(url)
    
    device = m.devices.getDevice(serial)
    client = m.networks.getNetworkClient(network, id)
    client['firstSeen'] = datetime.fromtimestamp(client['firstSeen']).isoformat()
    client['lastSeen'] = datetime.fromtimestamp(client['lastSeen']).isoformat()

    # Return the client's network traffic data over time. Usage data is in kilobytes. 
    traffic_hist = m.networks.getNetworkClientTrafficHistory(network, id, total_pages="all")
    # Return the client's daily usage history. Usage data is in kilobytes.
    usage_hist = m.networks.getNetworkClientUsageHistory(network, id)
    # Return the application usage data for clients. Usage data is in kilobytes. 
    app_usage = m.networks.getNetworkClientsApplicationUsage(network, [id], total_pages="all")

    print(traffic_hist)
    print(usage_hist)
    print(app_usage)

    connections = []
    for n in settings['networks']:
        try:
            c = m.networks.getNetworkClient(n['id'], id)
            if 'id' in c:
                clients = m.networks.getNetworkClients(n['id'], total_pages='all', perPage=100)
                for client in clients:
                    if client['id'] == id:
                        d = m.devices.getDevice(client['recentDeviceSerial'])
                        connections += [{
                            'firstSeen' : datetime.fromtimestamp(c['firstSeen']).isoformat(),
                            'lastSeen' : datetime.fromtimestamp(c['firstSeen']).isoformat(),
                            'mac' : c['recentDeviceMac'],
                            'serial' : d['serial'],
                            'model' : d['model'],
                            'name' : d['name'],
                            'network' : n['name']
                        }]
        except Exception as e:
            print(e)

    print(connections)

    return render_template('client.html', traffic=traffic_hist, usage=usage_hist, app=app_usage[0]['applicationUsage'], device=device, client=client, connections=connections)


#Settings
@app.route('/settings', methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        apikey = request.form.get('apikey')
        settings = getJson("settings.json")
        settings['apikey'] = apikey
        writeJson("settings.json", settings)

        m = DashboardAPI(apikey)
        networks = []
        for o in m.organizations.getOrganizations():
            for n in m.organizations.getOrganizationNetworks(o['id']):
                networks += [{"org" : o['name'], "name": n['name'], "id":n['id']}]
        return render_template('settings.html', hiddenLinks=True, settings=getJson("settings.json"), apikeyset=True, networks=networks)

    try:
        return render_template('settings.html', hiddenLinks=True, settings=getJson("settings.json"), apikeyset=False, networks=[])
    except Exception as e: 
        print(e)  
        return render_template('settings.html', hiddenLinks=True)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=7777, debug=True)