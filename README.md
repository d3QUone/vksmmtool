<b>VKSMM</b> is a cool way to check the best posts from your groups
<hr>
<b>How to run:</b>

1) Setup all required modules on your server 

2) Create project folders:

\vksmmtool <br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\templates <br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\static <br>

Don't forget to add graphic files to "\static" folder:<br>
```
"none.png", "Comment-Icon-copy.png", "Comment-Icon-sort.png", "Like-Icon-copy.png"
"Like-Icon-sort.png", "Repost-Icon-copy.png", "Repost-Icon-sort.png"
```

3) Fill them and setup DB via bash from \vksmmtool-folder:

```bash
python

>>> import server
>>> server.init_db()
```

4) Run parser in a screen

<code>screen python vkparser.py</code>

5) Setup NGNIX-server and Gunicorn, following  <a href="https://realpython.com/blog/python/kickstarting-flask-on-ubuntu-setup-and-deployment/">this article</a>, restart it and run app from the project folder, e.g:

```bash
sudo /etc/init.d/nginx restart
cd user/vksmmmtool
screen gunicorn -w 2 -b localhost:8000 server:app
```
and Control + A + D to leave screen working

<hr>
<a href="http://vksmm.info/" target="_blank"><b>Check it </b></a> (http://vk.com/  account is required)
