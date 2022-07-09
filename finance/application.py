import os
from re import sub
from decimal import Decimal

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():

    totalSharesValue = 0
    userId = session["user_id"]
    sqlStr = "SELECT upper(symbol) as symbol, Upper(share_name) as name, share_qty as shares, "
    sqlStr = sqlStr + " unit_price as price, total_price as total "
    sqlStr = sqlStr + " FROM user_stocks WHERE user_id = ? "
    rows_stock = db.execute(sqlStr, userId)

    sqlStr = "SELECT IFNULL(sum(total_price), 0) as totalSharesValue "
    sqlStr = sqlStr + "FROM user_stocks WHERE user_id = ? "
    rowTotValue = db.execute(sqlStr, userId)

    if len(rowTotValue) > 0:
        totalSharesValue = float(rowTotValue[0]["totalSharesValue"])

    sqlStr = "SELECT 'Cash' as symbol, cash as total "
    sqlStr = sqlStr + " FROM users WHERE id = ? "
    rows = db.execute(sqlStr, userId)
    if len(rows) > 0:
        totalCash = rows[0]["total"]
        totalSharesValue = float(totalSharesValue) + float(totalCash)

    """Show portfolio of stocks"""
    return render_template("index.html", rows_stocks=rows_stock, rows=rows, totalSharesValue=totalSharesValue)
    

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    unitPrice = 0.0
    userCash = 0.0
    totalValue = 0.0
    currentQty = 0
    userId = session["user_id"]

    symbol = request.form.get("symbol")
    shareQty = request.form.get("shares")

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        if not symbol or not shareQty:
            return apology("wrong information A", 400)
        elif not shareQty.isnumeric():
            return apology("wrong information B", 400)
        elif not shareQty.isdigit():
            return apology("wrong information C", 400)
        else:
            print("4")
            jDict = lookup(symbol)
            # Query database for cash in the user account
            if jDict == None:
                return apology("Share does not exist", 400)
            else:
                shareName = jDict["name"]
                price = usd(jDict["price"])
                unitPrice = float(sub(r'[^\d.]', '', price))
                totalValue = float(unitPrice) * float(shareQty)

                rows = db.execute("SELECT cash FROM users WHERE id = ?", userId)
                if len(rows) == 1:
                    userCash = rows[0]["cash"]
                    if totalValue <= float(userCash):
                        newCash = float(userCash) - totalValue
                        db.execute("UPDATE users SET cash = ? where id = ?", newCash, session["user_id"])

                        # insert history
                        sqlStr = "INSERT INTO user_history_stocks(user_id, symbol, operation, share_qty, unit_price, total_price) "
                        sqlStr = sqlStr + "VALUES(?, upper(?), ?, ?, ?, ?)"
                        db.execute(sqlStr, userId, symbol, "Bought", shareQty, unitPrice, totalValue)

                        sqlStr = "SELECT IFNULL(sum(share_qty), 0) as userShareQty "
                        sqlStr = sqlStr + "FROM user_stocks WHERE user_id = ? "
                        sqlStr = sqlStr + "and upper(symbol) = upper(?) "
                        rows_userQty = db.execute(sqlStr, userId, symbol)

                        if len(rows_userQty) > 0:

                            if float(rows_userQty[0]["userShareQty"]) == 0:
                                currentQty = 0
                                sqlStr = "INSERT INTO user_stocks(user_id, symbol, share_name, share_qty, unit_price, total_price) "
                                sqlStr = sqlStr + "VALUES(?,upper(?),upper(?),?,?,?)"
                                db.execute(sqlStr, userId, symbol, shareName, shareQty, unitPrice, totalValue)

                            else:
                                currentQty = float(rows_userQty[0]["userShareQty"])
                                totalValue = float(unitPrice) * (float(currentQty) + float(shareQty))
                                sqlStr = "UPDATE user_stocks set share_qty = share_qty + ?,  "
                                sqlStr = sqlStr + "unit_price = ?, "
                                sqlStr = sqlStr + "total_price = ? "
                                sqlStr = sqlStr + "where user_id = ? "
                                sqlStr = sqlStr + "and upper(symbol) = upper(?) "
                                db.execute(sqlStr, shareQty, unitPrice, totalValue, userId, symbol)

                        # Redirect user to home page
                        return redirect("/")
                    else:
                        return apology("Not enough cash", 400)
                else:
                    return apology("Error reading the user cash", 400)
    else:
        return render_template("buy.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    unitPrice = 0.0
    userCash = 0.0
    totalValue = 0.0
    userId = session["user_id"]
    userQty = 0.0

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        symbolToSell = request.form.get("symbol")
        shareQtyToSell = request.form.get("shares")
        sqlStr = "SELECT sum(share_qty) as userShareQty "
        sqlStr = sqlStr + "FROM user_stocks WHERE user_id = ? "
        sqlStr = sqlStr + "and upper(symbol) = upper(?) "
        rows_userQty = db.execute(sqlStr, userId, symbolToSell)

        if len(rows_userQty) == 1:
            userQty = float(rows_userQty[0]["userShareQty"])
            jDict = lookup(symbolToSell)
            sellPrice = jDict["price"]
            totalSell = float(sellPrice) * float(shareQtyToSell)
            if float(shareQtyToSell) < float(userQty):
                sqlStr = "UPDATE user_stocks set share_qty = share_qty - ?,  "
                sqlStr = sqlStr + "total_price = unit_price * (share_qty - ?)  "
                sqlStr = sqlStr + "where user_id = ? "
                sqlStr = sqlStr + "and upper(symbol) = upper(?) "
                db.execute(sqlStr, shareQtyToSell, shareQtyToSell, userId, symbolToSell)

            if float(shareQtyToSell) == float(userQty):
                sqlStr = "DELETE FROM user_stocks "
                sqlStr = sqlStr + "where user_id = ? "
                sqlStr = sqlStr + "and symbol = ? "
                db.execute(sqlStr, userId, symbolToSell)

            if float(shareQtyToSell) > float(userQty):
                return apology("Quantity to sell is too big")
            else:
                db.execute("UPDATE users SET cash = (cash + ?) where id = ?", totalSell, userId)
                # insert history
                sqlStr = "INSERT INTO user_history_stocks(user_id, symbol, operation, share_qty, unit_price, total_price) "
                sqlStr = sqlStr + "VALUES(?, upper(?), ?, ?, ?, ?)"
                db.execute(sqlStr, userId, symbolToSell, "Sell", shareQtyToSell, sellPrice, totalSell)

                # Redirect user to home page
                return redirect("/")
        else:
            return apology("Share not available to sell")
    else:
        sqlStr = "SELECT distinct upper(symbol) as symbol "
        sqlStr = sqlStr + "FROM user_stocks WHERE user_id = ? "
        rows_stocks = db.execute(sqlStr, userId)
        return render_template("sell.html", rows_stocks=rows_stocks)


@app.route("/history")
@login_required
def history():
    userId = session["user_id"]

    sqlStr = "SELECT UPPER(symbol) as symbol, operation, unit_price as price, "
    sqlStr = sqlStr + "CASE "
    sqlStr = sqlStr + "WHEN operation = 'Bought' THEN share_qty "
    sqlStr = sqlStr + "ELSE (share_qty * -1) "
    sqlStr = sqlStr + "END as shares, DateTime_Transacted as transacted "
    sqlStr = sqlStr + "FROM user_history_stocks WHERE user_id = ?  order by DateTime_Transacted DESC "
    rows_stocks = db.execute(sqlStr, userId)
    if len(rows_stocks) > 0:
        return render_template("history.html", rows_stocks=rows_stocks)
    else:
        return apology("No history to show")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():

    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Share Symbol is a must", 400)
        else:
            quote_result = ""
            jDict = lookup(symbol)
            if jDict != None:
                price = usd(jDict["price"])
                quote_result = "A share of " + jDict["name"] + " " + jDict["symbol"] + " - "
                quote_result = quote_result + "Costs: " + price
                return render_template("quote.html", quote_result=quote_result)
            else:
                return apology("Share Symbol does not exist!", 400)
    else:
        return render_template("quote.html")
        

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 400)
        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 400)
        elif not confirmation:
            return apology("must provide a password confirmation", 400)
        # Ensure username doesn't exists before
        elif len(rows) == 1:
            return apology("username already exist.", 400)

        # Ensure the password is correct
        elif password != confirmation:
            return apology("passwords must match", 400)
        else:
            username = request.form.get("username")
            passw = generate_password_hash(request.form.get("password"))
            cash = 10000

            # add a new user to the database
            db.execute("INSERT INTO users (username, hash, cash) VALUES (?, ?, ?)", username, passw, cash)
            username = None
            passw = None
            cash = None
            result = 'Inserted Successfuly'

            # Query database for username
            rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

            # Ensure username exists and password is correct
            if len(rows) != 1:
                return apology("User not created", 404)
            else:
                # Remember the reecent user already created
                session["user_id"] = rows[0]["id"]
                # Redirect user to home page
                return redirect("/")
    else:
        return render_template("register.html")
        

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
