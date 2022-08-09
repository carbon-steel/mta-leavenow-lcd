#!/usr/bin/python3
# =============================================================================
#
# Leave Now - Encouraging stress-free travel to your local MTA subway station
# by knowing when it's time to leave home.
#
# Version 2.0 7-Mar-2022 by Rob D <http://github.com/rob718/mta-leavenow>
#
# == Change Log
# v2.0 7-Mar-2022: Rewritten using NYCT-GTFS library by Andrew Dickinson
#
# == Prerequisites
# NYCT-GTFS library https://github.com/Andrew-Dickinson/nyct-gtfs
#
# == License
# This is free and unencumbered software released into the public domain.
#
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
#
# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# For more information, please refer to <http://unlicense.org>
# =============================================================================
from nyct_gtfs import NYCTFeed
import threading
import datetime
import time
from lib.lcd import drivers

# Specifiy your feed access key. See https://api.mta.info/#/AccessKey
my_api_key = ''
if len(my_api_key) == 0:
   raise Exception('You must fill out an API key!")

# Which subway feed should be used for your stop?
# List of feeds: https://api.mta.info/#/subwayRealTimeFeeds
my_feed_url = 'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm'

# What station do you want to monitor? 
# http://web.mta.info/developers/data/nyct/subway/Stations.csv
#
# Determine "GTFS Stop ID" and suffix direction.
# For example 'R31N' for "Northbound Atlantic Av - Barclays Ctr"
my_stop_id = ['R31N', 'R31S']

# How long does it take in minutes to walk to this station?
my_walking_time = 2

# How long should we wait before refreshing MTA feed? MTA says feeds are
# generated every 30 seconds, so anything less wouldn't make sense.
# Feed size (from each pull) can be around 500 kiB. Therefore expect to pull
# around 350 MiB in a 24 hour period.
# On a RaspPi Zero, expect a turn-around of retrieving and processing data
# to be around 15 seconds.
feed_refresh_delay = 65


def ticker():
    global north_text
    global south_text
    current_north_text = None
    current_south_text = None
    prev = ""
    updated = ""
    current = ""

    def write_screen():
        display.lcd_clear()
        display.lcd_display_string(current, 1)
        display.lcd_display_string("Update: " + updated, 2)
        display.lcd_display_string(north_text, 3)
        display.lcd_display_string(south_text, 4)

    # Don't stop! Continously loop forever (or until you kill it!)
    while True:
        current = time.strftime('%b %d %H:%M')
        if current != prev:
            prev = current
            write_screen()
        # Determine if ticker text has changed since last update
        if current_north_text != north_text or current_south_text != south_text:
            updated = current
            current_north_text = north_text
            current_south_text = south_text

            # Update console (or log)
            # print(north_text, south_text)
            write_screen()
        else:
            time.sleep(0.02)


def get_trains(action):
    global feed
    
    # Determine if we should do a new pull or a refresh according to NYCT-GTFS
    # library instruction. We must also update feed references as existing
    # objects are not modified by refresh()
    if action == 'refresh':
        feed.refresh()
        trains = feed.trips[0]
    else:
        feed = NYCTFeed(my_feed_url, api_key=my_api_key)
    
    # filter feed to only trains headed to our stop and are moving
    trains = feed.filter_trips(headed_for_stop_id=my_stop_id, underway=True)

    # find trains those next stop is our stop
    # (i.e. we don't want those earlier down the track)
    arrivals_north = []
    arrivals_south = []
    for train_num in range(len(trains)):
        stops = trains[train_num].stop_time_updates
        for stop in stops:
            if stop.stop_id == my_stop_id[0]:

                # get arrival time (in minutes) and train number.
                # Ignore trains arriving too soon
                arrival_time = int((stop.arrival - datetime.datetime.now())
                    .total_seconds() / 60)
                if arrival_time >= my_walking_time:
                    arrivals_north.append([arrival_time, trains[train_num].route_id])

    for train_num in range(len(trains)):
        stops = trains[train_num].stop_time_updates
        for stop in stops:
            if stop.stop_id == my_stop_id[1]:

                # get arrival time (in minutes) and train number.
                # Ignore trains arriving too soon
                arrival_time = int((stop.arrival - datetime.datetime.now())
                    .total_seconds() / 60)
                if arrival_time >= my_walking_time:
                    arrivals_south.append([arrival_time, trains[train_num].route_id])

    arrivals_north.sort()
    arrivals_south.sort()
    return (arrivals_north, arrivals_south)


def main():
    global north_text
    global south_text
    global display

    display = drivers.Lcd()
    display.lcd_clear()
    north_text = ('Getting train data...')
    south_text = ""

    # create seperate thread for ticker (tape)
    tape = threading.Thread(target=ticker)
    tape.daemon = True
    tape.start()

    # get train data and update ticker
    trains_north, trains_south = get_trains('new')
    while True:
    
        # build ticker accordingly; show first two arrivals if more than one train
        # array content: trains[arrival time in minutes][train number e.g. "D"]
        if trains_north:
            if len(trains_north) > 1:
                north_text = ('Nor ({}):{}\', ({}):{}\''
                    .format(trains_north[0][1], trains_north[0][0],trains_north[1][1], trains_north[1][0]))
            else:
                north_text = ('Nor ({}) in {}\''.format(trains_north[0][1], trains_north[0][0]))
        else:
            north_text = ('No Nor train data.')


        if trains_south:
            if len(trains_south) > 1:
                south_text = ('Sou ({}):{}\', ({}):{}\''
                    .format(trains_south[0][1], trains_south[0][0],trains_south[1][1], trains_south[1][0]))
            else:
                south_text = ('Sou ({}) in {}\''.format(trains_south[0][1], trains_south[0][0]))
        else:
            south_text = ('No Sou train data.')


        time.sleep(feed_refresh_delay)
        trains_north, trains_south = get_trains('refresh')

if __name__ == '__main__': main()
