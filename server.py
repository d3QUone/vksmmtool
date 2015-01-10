from flask import Flask, make_response, jsonify, request, g
from flask import render_template, redirect, url_for
from contextlib import closing
import sqlite3
import time
import requests
import json
import os

app = Flask(__name__)
app.config.update(
    DATABASE = 'base.db', #/root/vksmmtool/base.db
    DEBUG = False
    #SERVER_NAME = "178.62.64.47:5000"
)

def connect_db():
    return sqlite3.connect(app.config['DATABASE'])


# run once from bash to setup tables
def init_db():
    with closing(connect_db()) as db:
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
    #db = connect_db()
    #db.execute("insert into userinfo (username, password, status) values ('admin1', 'zxC_aQL2', 'ok')") #good
    #db.commit()


@app.before_request
def before_request():
    g.db = connect_db()


@app.teardown_request
def teardown_request(exception):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()


# --------- VK SMM TOOLS ---------

@app.route('/')
@app.route('/vk', methods = ['GET'])
def login_demo_page():
    error = request.args.get('error')
    # detailed static params; render link
    client_id = "4260316"
    redirect_uri = url_for('parse_vk_responce', _external=True)
    link = "https://oauth.vk.com/authorize?"
    link += "client_id=" + client_id
    link += "&scope=groups"
    link += "&redirect_uri=" + redirect_uri
    link += "&response_type=code&v=5.27"
    return render_template('index.html', link = link, error = error)


# vk auth module
@app.route('/vk_login', methods = ['GET'])
def parse_vk_responce():
    code = request.args.get('code')
    if code:
        try:
            client_id = "4260316"
            client_secret = "x9Qe9JKVfoTG57LMKUgH"
            redirect_uri = url_for('parse_vk_responce', _external=True)
            # render link and get auth_token, user_id
            req = "https://oauth.vk.com/access_token?"
            req += "client_id=" + client_id
            req += "&client_secret=" + client_secret
            req += "&code=" + code
            req += "&redirect_uri=" + redirect_uri
            res = requests.get(req).json()

            # personal data
            user_id = res["user_id"]
            access_token = res["access_token"]

            # delete old personal data first
            g.db.execute("delete from userinfo where user_id = " + str(user_id))
            g.db.commit()

            # + save new (its faster:)
            g.db.execute("insert into userinfo (user_id, auth_token) values ({0}, '{1}')".format(int(user_id), access_token))
            g.db.commit()

            # delete old groups
            g.db.execute("delete from groups where user_id = " + str(user_id))
            g.db.commit()
            
            # load fresh groups from account; 
            req = "https://api.vk.com/method/execute.get_all_groups?access_token=" + access_token
            buf = requests.get(req).json()["response"]
            group_ids = ",".join(str(xi) for xi in buf)
            
            req = "https://api.vk.com/method/groups.getById?group_ids=" + str(group_ids)
            groups = requests.get(req).json()["response"]

            for item in groups:
                g.db.execute("insert into groups (user_id, group_id, screen_name, picture) values ({0}, {1}, '{2}', '{3}')".format(int(user_id), int(item["gid"]), item["screen_name"], item["photo_medium"]))
                g.db.commit()
        except Exception as e:
            print "/vk_login err:", e
                
        return redirect(url_for('personal_page', user_id = user_id, token = access_token))
    else:
        return "Something has gone wrong<br><a href=" + str(url_for('vk')) + ">go back to login page</a>"


# vk personal page render
@app.route('/personal_page', methods = ['GET', 'POST'])
def personal_page():
    if request.method == 'GET':
        user_id = request.args.get("user_id")
        token = request.args.get("token")
    else:
        user_id = request.form['user_id']
        token = request.form['token']
        link_to_group = request.form['link_to_group']
    
    data = g.db.execute("select * from userinfo where user_id = {0}".format(user_id)).fetchall()[0]
    # data = [user_id, picture, auth_token]
    
    if len(data) > 0:
        if token == data[2]:
            add_error = None
            '''
            # do I really need to add groups manually ???
            
            if request.method == 'POST':
                # add group from page-form
                try:
                    # get group id by name:
                    link_to_group = link_to_group.split("/")
                    gr_name = link_to_group[len(link_to_group) - 1]
                    
                    url = "https://api.vk.com/method/groups.getById?group_id=" + gr_name + "&v=5.27"
                    req = requests.get(url).json()
                    item = req['response'][0]

                    new_append = {"id": item["id"], "name": item["name"], "screen_name": item["screen_name"]}
                    if new_append not in data["groups"] + data["manual_groups"]:
                        data["manual_groups"].append(new_append)
                    else:
                        add_error = "exist"
                        
                except Exception as e:
                    print "post err:", str(e)
                    add_error = "bad"
            '''
            
            all_groups = g.db.execute("select * from groups where user_id = " + str(user_id)).fetchall()
            # ...[j] = [user_id, group_ip, screen_name, picture]
            posts = {}
            group_list = []
            for group_item in all_groups:
                try:
                    group_id = group_item[1]
                    screen_name = group_item[2]

                    req = "https://api.vk.com/method/execute.group_name?access_token=" + token + "&id=" + str(group_id)
                    name = requests.get(req).json()["response"][0]

                    group_list.append({"name": name, "screen_name": screen_name, "id": group_id})

                    # SORTING HERE!
                    content = g.db.execute("select like, link, comm, repo from postinfo where group_id = " + str(group_id) + " order by like desc").fetchall()
                    # ...[j] = [group_id, picture, content=None, link, like, comm, repo] -- full
                    # ...[j] = [like, link, comm, repo] -- now
                    length = len(content)
                    if length < 100:
                        posts[screen_name] = content
                    else:
                        i = 0
                        buf = []
                        while i < 100:
                            buf.append(content[i])
                            i += 1
                        posts[screen_name] = buf
                except Exception as ex:
                    print "loading err: ", ex, ", group:", screen_name
            try:
                # load actual username
                req = "https://api.vk.com/method/execute.name_pic?access_token=" + token + "&id=" + str(user_id)
                username = requests.get(req).json()["response"]["name"] # ["picture"] -- avatar 100px
                        
                # load work stats
                f = open("statistics.txt", "r")
                stats = json.loads(f.read())
                f.close()
                return render_template("vk_personal.html", username = username, group_list = group_list,
                                       manual_groups = None, posts = posts, stats = stats,
                                       user_id = user_id, token = token, add_error = add_error)
            except Exception as ex:
                return "return err: " + str(ex)
    
    return redirect(url_for('login_demo_page', error = "bad"))


# detailed content of group (all posts + current stats)
@app.route("/detail", methods = ["GET"])
def group_detail():
    group_id = request.args.get("group_id")
    if group_id:
        try:
            req = "https://api.vk.com/method/groups.getById?group_id=" + str(group_id)
            name = requests.get(req).json()["response"][0]["name"]
            #print "name:", name

            # + sorting
            posts = g.db.execute("select like, link, comm, repo from postinfo where group_id = " + str(group_id) + " order by like desc").fetchall()
            #                 0        1        2      3     4      5     6
            # posts[j] = [group_id, picture, content, link, like, comm, repo]  <-- if *
            return render_template("vk_group_detailed.html", group_name = name,
                                   amount = len(posts), post_list = posts)
        except Exception as ex:
            print "detail load:", str(ex)
            return "Sorry, something wrong... "
    else:
        return redirect(url_for("login_demo_page", error = "bad"))


# new design concept 
#                                       --demo page with-OUT JS (YET)
@app.route('/demo', methods = ['GET'])
def show_demo_page():
    user_id = request.args.get('user_id')
    if user_id: #and type(user_id) is type(13) <-- add a checkup
        print "user_id", user_id, "is connected, <type>:", type(user_id)
        # new design template...
        
        # load all groups
        groups = g.db.execute("select group_id from groups where user_id = " + str(user_id)).fetchall()
        group_ids = ""
        for group in groups:
            group_ids += str(group[0]) + ","

        # still in debug    
        try:
            req = "https://api.vk.com/method/groups.getById?group_ids=" + group_ids
            names = requests.get(req).json()["response"]

            # load offset=0, count=100 from first group_id
            group_id = request.args.get('group_id') # heetriy method
            if group_id is None:
                group_id = groups[0][0]

            #!!! a gap (to load current group)
            current_group_name = None
            current_group_picture = None
            group_list = []
            for name in names:
                group_list.append([name["gid"], name["name"], name["photo_medium"]])
                if str(name["gid"]) == str(group_id):
                    current_group_name = name["name"]
                    current_group_picture = name["photo_medium"]
            
            posts = g.db.execute("select like, repo, comm, link from postinfo where group_id = " + str(group_id) + " order by like desc limit 100").fetchall()

            # + create buttons for navigations (if offset < 0 or count > len(all_posts): button = None
            #                                                            posts on curr page (e.g. 99)
            return render_template("demo.html", group_list = group_list, posts = posts, user_id = user_id, 
                                   current_group_name = current_group_name, current_group_picture = current_group_picture)
        except Exception as e:
            return "Error: " + str(e)
    else:
        return "sorry"
    
'''
# ajax endpoint
@app.route('/update', methods = ['POST'])
def update_page():
    group_id = request.form['group_id']
    offset = request.form['offset']
    #....
    res = {}
    return jsonify(res)
'''


# --- ERRORS ---

@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'code': 404, 'message': 'Page not found'}), 404)


if __name__ == '__main__':
    app.run(host='0.0.0.0')
