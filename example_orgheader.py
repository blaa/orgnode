#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Parse org-mode agendas, task lists, etc. and return simple reminders
to be included in environment status bar or shell. In general:
Generate agenda view for a shell.

License: MIT
Author: Tomasz bla Fortuna /bla at thera dot be/
"""

import datetime as dt
import os
import Orgnode as orgnode
import itertools

##
# Config
agenda_files = [
    "tasks.org",
]

base = "/home/USERDIR/.org/"

# Look 5 days ahead
horizont = 5.0

# Mark tasks with time, happening in less than X hours
mark_in = 3.0

todos = ["TODO", "DONE", "DELEGATED", "CANCELLED", "DEFERRED"]
todos_ignored = ["DONE", "CANCELLED", "DEFERRED"]

def load_data():
    "Load data from all agendas using orgnode"
    db = []
    for agenda in agenda_files:
        path = os.path.join(base, agenda)
        db += orgnode.makelist(path, todo_default=todos)
    return db


def until(date, relative):
    """
    Return time difference taking into account that date might not have a time given.
    If so - assume end of day. `relative' always has a time.
    """

    # Decorate with time
    if type(date) == dt.date:
        date = dt.datetime(date.year, date.month, date.day, 23, 59, 59)

    delta = (date - relative).total_seconds()
    if delta < 0:
        return None, None # Past event

    return date, delta / 60.0 / 60.0 / 24.0


def closest(date_list, relative):
    "Find closest future event relative to a given date"
    # Closest date - original
    closest_date = None

    # Closest date converted to datetime
    closest_converted_date = None

    # Time delta for closest date
    closest_delta = None

    for date in sorted(date_list):
        converted_date, days = until(date, relative)
        if days is None:
            # Past event
            continue

        closest_date = date
        closest_converted_date = converted_date
        closest_delta = days
        break

    return (closest_converted_date, closest_date, closest_delta)


def get_incoming(db):
    """
    Parse all events and gather ones happening in the near
    future (set by horizont)

    Takes into account any possible dates, can report the same
    event multiple times for different dates.
    """
    today = dt.datetime.today()

    incoming = []

    for entry in db:
        if entry.todo in todos_ignored:
            continue

        def analyze_dates(dates, datetype):
            closest_converted_date, closest_date, closest_delta = closest(dates, relative=today)

            if closest_delta is not None and closest_delta < horizont:
                incoming.append((closest_converted_date, {
                    'eventtype': datetype,
                    'delta': closest_delta,
                    'closest_date': closest_date,
                    'closest_converted_date': closest_converted_date,
                    'entry': entry,
            }))

        analyze_dates(entry.datelist, 'TIMESTAMP')

        if entry.rangelist:
            starts = [dr[0] for dr in entry.rangelist]
            analyze_dates(starts, 'RANGE')

        scheduled = entry.Scheduled()
        deadline = entry.Deadline()

        if scheduled:
            analyze_dates([scheduled], "SCHEDULED")

        if deadline:
            analyze_dates([deadline], "DEADLINE")
    return incoming


def report_stat(incoming_list):
    u"Create a simple statistic for following days"
    incoming_list.sort()

    now = dt.datetime.now()
    eo_today = dt.datetime(now.year, now.month, now.day, 23, 59, 59)
    eo_tomorrow = eo_today + dt.timedelta(days=1)

    counted = set()

    stat_today = 0
    stat_tomorrow = 0
    stat_total = 0

    for incoming in incoming_list:
        closest_converted_date, data = incoming
        if data['entry'] in counted:
            continue # Count once, earliest entry
        counted.add(data['entry'])

        if closest_converted_date <= eo_today:
            stat_today += 1
        elif closest_converted_date <= eo_tomorrow:
            stat_tomorrow += 1

        stat_total += 1

    stat_rest = stat_total - stat_today - stat_tomorrow

    s = ""
    if stat_today:
        s += str(stat_today)
    if stat_tomorrow:
        s += '->%d' % stat_tomorrow
    if stat_rest:
        s += '-->%d' % stat_rest

    #s = "T %d->%d-->%d" % (stat_today, stat_tomorrow, stat_rest)
    return s


def report_incoming(incoming_list):
    u"Report incoming tasks for following days"
    if not incoming_list:
        return

    today = dt.datetime.today()
    incoming_list.sort()
    add_separator = False # Today separator

    if incoming_list[0][0].day == today.day:
        add_separator = True

    for incoming in incoming_list:
        closest_converted_date, data = incoming
        todo = data['entry'].todo or 'TASK'

        if add_separator and closest_converted_date.day != today.day:
            add_separator = False
            print "- EOD -"

        if data['eventtype'] == 'DEADLINE':
            marker = 'D'
        elif data['eventtype'] == 'SCHEDULED':
            marker = 'S'
        elif data['eventtype'] == 'RANGE':
            marker = 'R'
        else:
            marker = ' '

        if data['closest_date'] == data['closest_converted_date'] and data['delta']*8 < mark_in:
            marker += '-->'
        else:
            marker += '   '

        s = "%s %9s %-20s %s"
        s = s % (marker, todo, data['closest_date'],
                 data['entry'].headline[:60])

        print s


def main():
    u"Display raport and save statistics"
    db = load_data()
    incoming = get_incoming(db)

    report_incoming(incoming)
    rep = report_stat(incoming)
    with open('/home/bla/.xmonad/task_stat', 'w') as f:
        f.write(rep)


if __name__ == "__main__":
    main()
