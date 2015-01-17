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

3) Fill them and setup DB vis bash:

```bash
python
import server
server.init_db()
```

4) Run it in 2 screens (for example)

<code>screen python vkparser.py</code>

<code>screen python server.py</code>
<hr>
<a href="http://178.62.64.47:5000/" target="_blank"><b>Try pre-release version</b></a> (Vkontakte-account is required)
