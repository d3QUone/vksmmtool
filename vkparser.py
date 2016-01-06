__author__ = 'vladimir'

import os
import sys
import json
import time
from datetime import datetime

import requests
from logger import Logger

from database import select_query, update_query
from server import short_value


reload(sys)
sys.setdefaultencoding('utf8')

ver = "4a"
log = Logger("vksmm.parser")


def getA(group_id, auth_token=None, offset=0, count=100):
    """vk + requests interface"""
    if auth_token:
        url = "https://api.vk.com/method/execute.wall"
        data = {
            "i": "-{0}".format(group_id),
            "o": offset,
            "c": count,
            "access_token": auth_token
        }
    else:
        url = "https://api.vk.com/method/wall.get"
        data = {
            "owner_id": "-{0}".format(group_id),
            "offset": offset,
            "count": count,
            "v": "5.27"
        }
    res = requests.get(url, params=data)
    try:
        rjson = res.json()
        if "response" in rjson.keys():
            return rjson["response"]
        else:
            log.error(rjson["error"])
            return {"code": rjson["error"]["error_code"], "message": rjson["error"]["error_msg"]}
    except Exception as e:
        log.error("Requests error: {}, raw data: {}".format(e, res.text))
        return {"items": [], "count": 0}


def get_unique_groups(query, params=None):
    all_groups = []
    append = all_groups.append
    all_groups_raw = select_query(query, params)
    for item in all_groups_raw:
        if item[0] not in all_groups:
            append(item[0])
    log.info("fetched {} unique groups".format(len(all_groups)))
    return all_groups


def controller():
    processed_groups = []
    append = processed_groups.append
    while True:
        sql_request = "SELECT g.`group_id` FROM `groups` g ORDER BY g.`added` DESC"
        all_groups = get_unique_groups(sql_request)
        while len(all_groups) == 0:
            log.info("len all = 0")
            time.sleep(3)
            all_groups = get_unique_groups(sql_request)
        try:
            new_id = full_cycle_v2(processed_groups, all_groups)
            if new_id:
                append(new_id)
                log.info("new_id={} saved".format(new_id))
            else:
                log.info("ID=None, len processed={}, len all={}".format(len(processed_groups), len(all_groups)))
                time.sleep(3)
        except Exception as e:
            log.error("full_cycle: {}, len processed={}, len all={}".format(e, len(processed_groups), len(all_groups)))
            time.sleep(3)

        if len(all_groups) == len(processed_groups):
            log.info("all groups were parsed! {} groups total".format(len(processed_groups)).upper())
            del processed_groups[:]


def full_cycle_v2(processed_groups, all_):
    """Actually scans only 1 group, save parsed groups"""
    buf_all_groups = list(all_)
    i = 0
    chosen_id = -1
    while i < len(buf_all_groups):
        try:
            group_id = buf_all_groups[i]
            if group_id not in processed_groups:
                break
            else:
                buf_all_groups.pop(i)
        except Exception as e:
            log.error("Alert! Data error: {}. Raw: {}".format(e, buf_all_groups))
    try:
        if chosen_id == -1:
            group_id = buf_all_groups[0]  # -- first group of leftover
        else:
            group_id = chosen_id
    except Exception as e:
        log.error("choose_id exception: {}, buf_all_groups: {}".format(e, buf_all_groups))
        return None

    auth_token = None
    ret = getA(group_id, auth_token, 0, 1)

    # determine here if token is required
    ret_keys = ret.keys()
    if "count" in ret_keys:
        count = ret["count"]
    elif "code" in ret_keys:
        log.info("refreshing access_token...")
        user_id = select_query(
            "select g.`user_id` from `groups` g where g.`group_id`=%s order by g.`added` desc",
            (group_id, )
        )[0][0]
        auth_token = select_query(
            "select u.`auth_token` from `userinfo` u where u.`user_id`=%s",
            (user_id, )
        )[0][0]
        ret = getA(group_id, auth_token, 0, 1)
        if "count" in ret.keys():
            count = int(ret["count"])
        else:
            log.error("sorry... error_code={0}, message: {1}".format(ret["code"], ret["message"]))
            log.info(ret)
            return group_id
    else:
        return group_id
    log.info("--OK")
    update_query(
        "update groups set is_old=1 where group_id=%s",
        (group_id, )
    )
    update_query(
        "delete from postinfo where group_id=%s",
        (group_id, )
    )
    screen_name = select_query(
        "SELECT g.`screen_name` FROM `groups` g WHERE g.`group_id`=%s",
        (group_id, )
    )[0][0]
    log.info("screen_name: {}, group_id: {}, nums to parse: {}".format(screen_name, group_id, str(count)))
    if count > 30000 or count == 0:
        update_query(
            "delete from groups where group_id=%s",
            (group_id, )
        )
        log.info("removing this group from queue")
        return group_id
    try:
        req = "https://api.vk.com/method/groups.getById?group_id={0}".format(group_id)
        written_name = short_value(requests.get(req).json()["response"][0]["name"].replace("&amp;", "&"), 35)
    except Exception as ex:
        log.error("no written_name: {0}".format(ex))
        written_name = short_value(screen_name, 35)
    print "name: {}".format(written_name)

    # UPDATE GROUP-INFO IN THE STATS
    try:
        with open(os.path.join(os.getcwd(), "statistics.txt"), "r") as f:
            data = json.loads(f.read())
    except:
        data = {}
    data["name"] = written_name
    data["count"] = count
    data["group_id"] = group_id
    data["totalgroups"] = len(all_)
    with open(os.path.join(os.getcwd(), "statistics.txt"), "w") as f:
        f.write(json.dumps(data))

    # LOAD AND PROCESS VK-POSTS
    offset = count // 100 + 1
    for i in range(0, offset):
        posts = getA(group_id, auth_token, i * 100, 100)
        for post in posts["items"]:
            try:
                link = "http://vk.com/{0}?w=wall-{1}_{2}".format(screen_name, group_id, post["id"])
                try:
                    comm = post["comments"]["count"]
                except:
                    comm = 0
                try:
                    like = post["likes"]["count"]
                except:
                    like = 0
                try:
                    repo = post["reposts"]["count"]
                except:
                    repo = 0
                try:
                    picture = None
                    if "attachments" in post.keys():
                        a_type = post["attachments"][0]["type"]
                        if a_type in ["photo", "video"]:
                            picture = post["attachments"][0][a_type]["photo_130"]
                except Exception as ex:
                    picture = None
                update_query(
                    "insert into `postinfo` (`group_id`, `link`, `like`, `comm`, `repo`, `picture`) values (%s, %s, %s, %s, %s, %s)",
                    (group_id, link, like, comm, repo, picture)
                )
            except BaseException as ex:
                log.error("link error: {}, full post: {}, full response: {}".format(ex, post, posts))
        # UPDATE POSTs-INFO IN THE STATS
        with open(os.path.join(os.getcwd(), "statistics.txt"), "r") as f:
            data = json.loads(f.read())
        data["count"] -= len(posts["items"])
        if data["count"] < 0:
            data["count"] = 0
        with open(os.path.join(os.getcwd(), "statistics.txt"), "w") as f:
            f.write(json.dumps(data))
        time.sleep(0.05)

    # now load datas back and save only best 300
    limit = 100  # x3 = 300
    if count > limit * 3.05:
        ts = time.time()
        bestlikes = select_query(
            "select p.`group_id`, p.`link`, p.`like`, p.`comm`, p.`repo`, p.`picture` from `postinfo` p where p.`group_id`=%s order by p.`like` desc limit %s",
            (group_id, limit)
        )
        bestrepos = select_query(
            "select p.`group_id`, p.`link`, p.`like`, p.`comm`, p.`repo`, p.`picture` from `postinfo` p where p.`group_id`=%s order by p.`repo` desc limit %s",
            (group_id, limit)
        )
        bestcomms = select_query(
            "select p.`group_id`, p.`link`, p.`like`, p.`comm`, p.`repo`, p.`picture` from `postinfo` p where p.`group_id`=%s order by p.`comm` desc limit %s",
            (group_id, limit)
        )
        update_query(
            "delete from postinfo where group_id=%s",
            (group_id, )
        )

        toti = 0
        bestdatas = []
        append = bestdatas.append
        for post in bestlikes + bestrepos + bestcomms:
            if post not in bestdatas:
                toti += 1
                append(post)
                update_query(
                    "INSERT INTO `postinfo` (`group_id`, `link`, `like`, `comm`, `repo`, `picture`) VALUES (%s, %s, %s, %s, %s, %s)",
                    (post[0], post[1], post[2], post[3], post[4], post[5])
                )
                time.sleep(0.03)
        log.info("{} seconds to re save {} posts".format(int(time.time() - ts), toti))
    else:
        log.info("no re-save needed")
    return group_id


if __name__ == "__main__":
    log.info("vkparser v={} is running!".format(ver))
    controller()
