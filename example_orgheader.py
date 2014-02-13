#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Parse org-mode agendas, task lists, etc. and return simple reminders
to be included in environment status bar or shell.
"""

import datetime as dt
import os
import Orgnode as orgnode
import itertools
from collections import defaultdict

##
# Config
agenda_files = [
    "desktop.org",
    "tasks.org",
]

base = "/home/USERDIR/.org/"
task_stat_file = "/home/USERDIR/.xmonad/task_stat"
# Look 5 days ahead
horizont = 5.0

# Mark tasks with time, happening in less than X hours
mark_in = 3.0

todos = ["TODO", "DONE", "DELEGATED", "CANCELLED", "DEFERRED", "PROJECT"]
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
    # If negative - then a past event.
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

        closest_date = date
        closest_converted_date = converted_date
        closest_delta = days

        if closest_delta < 0:
            # Past event, iterate more
            continue
        # This is a first future event, do not check more.
        break

    return {
        'converted_date': closest_converted_date,
        'date': closest_date,
        'delta': closest_delta
    }


def get_incoming(db):
    """
    Parse all events and gather ones happening in the near
    future (set by horizont)

    Takes into account any possible dates, can report the same
    event multiple times for different dates.
    """
    today = dt.datetime.today()

    # Incoming events
    incoming = []

    # Past TODO events (SCHEDULED, DEADLINE) not marked as DONE
    unfinished = []

    # Things to show to remind you you're responsible
    # project entry -> {stats}
    projects = {}

    for entry in db:
        # Iterate over entries

        if entry.todo and entry.parent in projects:
            # Count number of tasks open within a project.
            # DONE, TODO, all types
            current_entry = entry
            while current_entry.parent:
                current_entry = current_entry.parent
                if current_entry in projects:
                    projects[current_entry][entry.todo] += 1

        # Now, ignore ones marked as "done/finished/closed"
        if entry.todo in todos_ignored:
            continue

        def analyze_dates(dates, datetype):
            data = closest(dates, relative=today)

            data.update({
                'eventtype': datetype,
                'entry': entry,
            })

            if data['delta'] is None:
                return # No dates
            elif data['delta'] < 0:
                # Past event
                unfinished.append((data['converted_date'], data))
            else:
                # Future event
                if data['delta'] <= horizont:
                    incoming.append((data['converted_date'], data))


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


        if entry.todo == "PROJECT":
            projects[entry] = defaultdict(lambda: 0)

    return incoming, unfinished, projects

def get_totals_stat(db):
    """
    Count all entries versus not ignored (opened).

    This is supposed to help push TODOs without a specified execution time.
    """
    count_total = 0
    count_open = 0

    for entry in db:
        # Iterate over entries

        if not entry.todo:
            # No designation at all, not a `task'
            continue

        if (entry.datelist or entry.Scheduled() or
            entry.Deadline() or entry.rangelist):
            # Has time - is already counted elsewhere
            continue

        count_total += 1

        # Ignore ones marked as "done/finished/closed"
        if entry.todo not in todos_ignored:
            count_open += 1

    return count_open, count_total


def report_stat(incoming_list, tasks_open, tasks_all):
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

    # Not timed
    s += " %d/%d" % (tasks_open, tasks_all)
    return s

def _get_marker(eventtype):
    if eventtype == 'DEADLINE':
        marker = 'D'
    elif eventtype == 'SCHEDULED':
        marker = 'S'
    elif eventtype == 'RANGE':
        marker = 'R'
    else:
        marker = ' '
    return marker

def _get_delta(delta, accurate=False):
    import math
    days = int(math.floor(delta))
    if days == 0:
        # Today
        if accurate:
            hours = math.floor(delta*24)
            if hours <= 0.1:
                return "NOW"
            if hours == 1:
                return "today in " + str(int(hours)) + " hour"
            if hours > 1:
                return "today in " + str(int(hours)) + " hours"
        else:
            return "today"
    elif days > 1:
        return "in " + str(days) + " days"
    elif days < 0:
        return str(-days) + " days ago"
    elif days == 1:
        return "1 day"


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

        marker = _get_marker(data['eventtype'])
        accurate = data['converted_date'] == data['date']
        # If equal - then the event has a time specified.
        if accurate and data['delta']*24 < mark_in:
            marker += '--> '
        else:
            marker += '    '

        s = "%s %9s %-20s %s"
        s = s % (marker, todo, _get_delta(data['delta'], accurate),
                 data['entry'].headline[:60])
        print s


def report_unfinished(unfinished_list):
    u"Report incoming tasks for following days"
    if not unfinished_list:
        return

    unfinished_list.sort()
    output = False

    for unfinished in unfinished_list:
        closest_converted_date, data = unfinished
        todo = data['entry'].todo

        if data['eventtype'] not in ['SCHEDULED', 'DEADLINE']:
            continue # Don't show things with plain timestamps

        marker = _get_marker(data['eventtype'])
        marker += ' DUE'
        accurate = data['converted_date'] == data['date']

        s = "%s %9s %-20s %s"
        s = s % (marker, todo, _get_delta(data['delta'], accurate),
                 data['entry'].headline[:60])

        output = True
        print s
    return output

def report_projects(projects):
    u"Report an open projects you're responsible for"
    if not projects:
        return

    print "PROJECTS:"
    for project, stat in projects.iteritems():
        print "  %-30s" % project.headline[:50],
        stats = " ".join(["%s=%d" % (k, v) for k, v in stat.iteritems()])
        if stats:
            print "(%s)" % stats
        else:
            print
    print


def main():
    u"Display raport and save statistics"
    db = load_data()
    incoming, unfinished, projects = get_incoming(db)
    tasks_open, tasks_all = get_totals_stat(db)

    report_projects(projects)

    output = report_unfinished(unfinished)
    if output and incoming:
        print
    report_incoming(incoming)

    print "[%d/%d]" % (tasks_open, tasks_all)



    rep = report_stat(incoming, tasks_open, tasks_all)
    with open(task_stat_file, 'w') as f:
        f.write(rep)


if __name__ == "__main__":
    main()
