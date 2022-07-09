import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///birthdays.db")
result = ""

@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":
        name = request.form.get("name")
        month = request.form.get("month")
        day = request.form.get("day")

        # TODO: Add the user's entry into the database
        if name and month and day and (1 <= int(month) <= 12) and (1 <= int(day) <= 31):
            # add a new record to the database
            db.execute("INSERT INTO birthdays (name, month, day) VALUES (?, ?, ?)", name, month, day)
            name = None
            month = None
            day = None
            result = 'Inserted Successfuly'
        if month and day:
            if (1 > int(month) > 12) or (1 > int(day) > 31):
                result = "Wrong information in Birthday"


    return redirect("/refresh")

@app.route("/refresh", methods=["GET", "POST"])
def refresh():
    rows = db.execute("SELECT name, substr('00'||month,-2) || '-' || substr(00||day, -2) as birthday FROM birthdays order by month, day")
    return render_template("index.html", rows = rows, result = result)

