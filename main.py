import discord
import random
from discord.ext import commands
import json
import os    
import asyncio
from aiohttp import web
import requests
import re
from bs4 import BeautifulSoup
import jmcomic
import traceback

jmcomic.JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN = False

option = jmcomic.create_option_by_str('''
client:
  postman:
    type: requests
''')

client = option.build_jm_client()


async def handle_home(request):
    return web.Response(text="Bot is alive!", status=200)

async def run_web_server():
    app = web.Application()
    app.router.add_get("/", handle_home)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"✅ Web server 監聽 Port: {port}")


intents=discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True  # 如果有用到成員資料
intents.messages = True
intents.voice_states = True
intents.reactions=True
intents.presences = True

#建置實體機器人
bot=commands.Bot(command_prefix=".",intents=intents)
bot.remove_command('help')
#符號那邊可以是空的,如果是空的會達成跟onmessage一樣效果

owneruser='bot製作人: 和泉紗霧'

TAG_DICT = {}
JSON_FILE_PATH = "db.raw.json"
pathpath=0
if os.path.exists(JSON_FILE_PATH):
    print("正在載入本地 EhTag 中文標籤資料庫...")
    with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
        tag_data = json.load(f)

    for data in tag_data.get("data", []):
        namespace = data.get("namespace")
        for tag_name, val in data.get("data", {}).items():
            raw_name = val.get("name", tag_name)
            # 剔除 Markdown 圖片標籤 ![...](...)
            clean_name = re.sub(r"!\[.*?\]\(.*?\)", "", raw_name).strip()

            TAG_DICT[f"{namespace}:{tag_name}"] = clean_name
            TAG_DICT[tag_name] = clean_name

    print("標籤資料庫載入完成！")
    pathpath=1
else:
    print(f"警告：找不到 {JSON_FILE_PATH}，將使用原始英文標籤。")

bot_avatar_url= 0

@bot.event
async def on_ready():
    print("online")
    await bot.change_presence(status=discord.Status.online,activity=discord.Game("蘿莉"))
    print(bot.user.name)
    print(bot.user.id)
    print('---------')
    global owneruser
    owneruser=f'\nbot製作人: {(bot.get_user(613578839372857383))}'
    global pathpath
    if pathpath==1:
        pathpath="標籤資料庫載入完成！"
    else:
        pathpath=f"警告：找不到 {JSON_FILE_PATH}，將使用原始英文標籤。"
    global bot_avatar_url
    bot_avatar_url=bot.user.display_avatar.url if bot.user else ""
    try:
        synced = await bot.tree.sync()
        slash=f"已成功同步 {len(synced)} 個 Slash 指令!"
    except Exception as e:
        slash=f"同步指令失敗: {e}"
    try:
        await bot.load_extension('blackjack')
        cogg=("已成功載入 blackjack 模組！")
    except Exception as e:
        cogg=(f"載入 21點 模組失敗: {e}")
    content='```'+'\n'+pathpath+'\n'+slash+'\n'+cogg+'```'
    await bot.get_channel(1533491542113779865).send(content)


@bot.event
async def on_message(msg):
    if msg.author.bot:
        return
    try:
        if msg.content=="ping" :
            await msg.channel.send(f"{bot.latency*1000}ms")
            return
        
        elif "aid-" in msg.content :
            index=msg.content.find("aid-")
            bbb = msg.content[index + 4 : index +14]
            album_id=""
            for i in bbb:
                if i.isdigit():
                    album_id+=i
                else:
                    break    
            m=await msg.reply('修復漫畫連結中...',mention_author=False)   
            def fetch_and_parse():
                res = requests.get(f'https://www.wn07.cfd/photos-index-aid-{album_id}.html', timeout=10)
                res.raise_for_status()
                return BeautifulSoup(res.text, features='lxml')
            try:
                soup = await asyncio.to_thread(fetch_and_parse)
            except Exception:
                await msg.reply('搜尋不到該番號或網站無法連線。',mention_author=False)
                return  

            # 安全地解析元素
            imgs = soup.select('img')
            if len(imgs) < 6:
                await msg.reply('頁面解析失敗（圖片數量不足或番號不存在）。',mention_author=False)
                return

            title = imgs[2].get('alt', '無標題')
            image = imgs[2].get('src', '')
            category = '未知'
            page_count = '未知'
            # 解析頁數
            labels = soup.select('label')
            for label in labels:
                text = label.text.strip()
                if '分類' in text:
                    parts = text.split('：')
                    if len(parts) > 1:
                        category = parts[1].strip()
                elif '頁數' in text:
                    parts = text.split('：')
                    if len(parts) > 1:
                        page_count = parts[1].split('P')[0].strip()

            # 建立 Embed
            ec = discord.Embed(
                title=title,
                description='點上面標題可直接開啟該網站',
                url=f'https://www.wnacg.com/photos-index-aid-{album_id}.html',
                colour=discord.Color.random()
            )
            ec.add_field(name='番號:', value=album_id, inline=True)
            ec.add_field(name='分類:', value=category, inline=True)
            ec.add_field(name='頁數:', value=page_count, inline=True)
            tag = []
            for a in soup.select('a'):
                href = a.get('href', '')
                # 通常標籤的連結會包含 tag 關鍵字
                if 'tag' in href:
                    tag_text = a.text.strip()
                    if tag_text and tag_text not in tag:  # 過濾重複與空字串
                        tag.append(tag_text)
            tags=tag[1:20]if tag else '無'
            tags_str = ', '.join(tags) if tags else '無'
            author=tag[0]
            ec.add_field(name='作者:', value=author, inline=True)
            ec.add_field(name='標籤:', value=tags_str, inline=False)
            
            if image:
                if image.startswith('http'):
                    img_url = image
                else:
                    clean_path = image.lstrip('/')
                    img_url = f'https://{clean_path}'
                ec.set_image(url=img_url)
                ec.set_footer(
                                text=
                                f'{owneruser}\n祝您使用愉快'
                            )
                if bot_avatar_url:
                    ec.set_thumbnail(url=bot_avatar_url)
                await m.delete()
                await msg.reply(embed=ec,mention_author=False)    

                try:
                    await msg.edit(suppress=True)
                except:
                    pass
            else:
                await m.delete()

        elif "e-hentai.org/g/" in msg.content :
                index=msg.content.find("e-hentai.org/g/")
                bbb = msg.content[index + 15 : index +24]
                album_id=""
                for i in bbb:
                    if i.isdigit():
                        album_id+=i
                    else:
                        break    
                m=await msg.reply('修復漫畫連結中...',mention_author=False)   
                headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
                        }
                match = re.search(r"https?://[^/]+/g/\d+/[^/]+/", msg.content)
                target_url = match.group(0)
                
                res = await asyncio.to_thread(
                    requests.get, target_url, headers=headers, timeout=10
                )

                if res.status_code != 200:
                    await msg.reply(f"無法存取頁面，狀態碼: {res.status_code}", mention_author=False)
                    return

                res.encoding = "utf-8"
                soup = BeautifulSoup(res.text, "html.parser")
            
                # 解析基本資訊
                title_el = soup.find("h1", id="gn")
                title = title_el.text.strip() if title_el else "無標題"
            
                cover_el = soup.select_one("#gd1 div")
                cover_url = ""
                if cover_el and "style" in cover_el.attrs:
                    match = re.search(r"url\((.*?)\)", cover_el["style"])
                    if match:
                        cover_url = match.group(1).strip("\"'")
            
                gdd_data = {}
                for row in soup.select("#gdd tr"):
                    cols = row.find_all("td")
                    if len(cols) == 2:
                        gdd_data[cols[0].text.strip().rstrip(":")] = (
                            cols[1].text.strip()
                        )
            
                posted_time = gdd_data.get("Posted", "未知")
                language = gdd_data.get("Language", "未知").split(" ")[0]
                length = gdd_data.get("Length", "未知")
                favorites = gdd_data.get("Favorited", "0")
            
                tags_by_group = {}
                for row in soup.select("#taglist tr"):
                    tc = row.find("td", class_="tc")
                    if tc:
                        group_name = tc.text.strip().rstrip(":")
                        tags_by_group[group_name] = [
                            t.text.strip() for t in row.select("td div a")
                        ]
            
                # 解析作者 (只取第一個)
                authors = tags_by_group.get("artist", []) + tags_by_group.get(
                    "group", []
                )
                author_str = authors[0] if authors else "未知"
            
                # 標籤查表與限制前 10 個
                raw_female_tags = tags_by_group.get("female", [])[:10]
                female_tags = [
                    TAG_DICT.get(f"female:{tag}", TAG_DICT.get(tag, tag))
                    for tag in raw_female_tags
                ]
            
                raw_male_tags = tags_by_group.get("male", [])[:10]
                male_tags = [
                    TAG_DICT.get(f"male:{tag}", TAG_DICT.get(tag, tag))
                    for tag in raw_male_tags
                ]
            
                parody_tags = tags_by_group.get("parody", [])
                if "original" in parody_tags:
                    parody_info = "原創 (Original)"
                elif parody_tags:
                    translated_parody = [
                        TAG_DICT.get(f"parody:{tag}", TAG_DICT.get(tag, tag))
                        for tag in parody_tags[:10]
                    ]
                    parody_info = ", ".join(translated_parody)
                else:
                    parody_info = "未知 / 未標示"
            
                ec = discord.Embed(
                    title=title,
                    description='點上面標題可直接開啟該網站',
                    url=target_url,
                    colour=discord.Color.random(),
                )
                if cover_url:
                    ec.set_image(url=cover_url)
            
                ec.add_field(name="作者", value=author_str, inline=True)
                ec.add_field(name="語言", value=language, inline=True)
                ec.add_field(name="頁數", value=length, inline=True)
                ec.add_field(name="收藏數", value=favorites, inline=True)
                ec.add_field(name="上傳時間", value=posted_time, inline=True)
                ec.add_field(name="戲仿/原作", value=parody_info, inline=True)
            
                ec.add_field(
                    name="女性標籤 (前10個)",
                    value=", ".join(female_tags) if female_tags else "無",
                    inline=False,
                )
                ec.add_field(
                    name="男性標籤 (前10個)",
                    value=", ".join(male_tags) if male_tags else "無",
                    inline=False,
                )
                ec.set_footer(
                                text=
                                f'{owneruser}\n祝您使用愉快'
                            )
                if bot_avatar_url:
                    ec.set_thumbnail(url=bot_avatar_url)
                await msg.reply(embed=ec,mention_author=False)
                await m.delete()
                try:
                    await msg.edit(suppress=True)
                except:
                    pass

        elif "https://telegra.ph" in msg.content :
                bbb=msg.content
                try:
                    # 將會阻塞的 requests.get 丟到背景執行緒
                    rr = await asyncio.to_thread(requests.get, bbb)
                    rr.raise_for_status()
                except Exception:
                    await msg.reply(
                        'telegram漫畫不能有除了連結以外的字符或空白鍵 或是 連結無效',
                        mention_author=False,
                    )
                    return  # 🔴 這裡一定要有 return，否則發生錯誤後程式會繼續往下跑而崩潰！

                m = await msg.reply('修復漫畫連結中...', mention_author=False)
                soup = BeautifulSoup(rr.text, features='lxml')
                title=soup.select('title')[0].text.split('- Page 1 –')[0]
                pages=len(soup.select('img'))
                image=soup.select('img')[0]['src']
                ec = discord.Embed(
                        title=f'{title}',
                        description='點上面標題可直接開啟該網站',
                        url=bbb,
                        colour=discord.Color.random()
                    )
                ec.add_field(name='頁數:', value=pages, inline=False)
                ec.set_image(url=image)
                ec.set_footer(
                                text=
                                f'{owneruser}\n祝您使用愉快'
                            )
                if bot_avatar_url:
                    ec.set_thumbnail(url=bot_avatar_url)
                await m.delete()
                await msg.reply(embed=ec,mention_author=False)
                try:
                    await msg.edit(suppress=True)
                except:
                    pass


        elif "18comic.vip/album/" in msg.content :
            
            index = msg.content.find("18comic.vip/album/")
            bbb = msg.content[index + 18 : index + 28]
            album_id = ""
            for i in bbb:
                if i.isdigit():
                    album_id += i
                else:
                    break
            m=await msg.reply('修復漫畫連結中...',mention_author=False)        
                
            try:
                album = client.get_album_detail(album_id)
            except:
                await msg.reply('無此漫畫 請重新檢查',mention_author=False)
                await m.delete()
                return
        
            chapter_count = len(album)
            is_single = (chapter_count <= 1)
        
            pages_info = None
            desc_info = None
        
            if is_single:
                # 單本/單話：抓取頁數資訊
                if chapter_count > 0:
                    first_photo_summary = album[0]
                    photo_detail = client.get_photo_detail(first_photo_summary.photo_id)
                    pages_info = f"{len(photo_detail)} 頁"
                else:
                    pages_info = "未知"
            else:
                # 連載作品：抓取作品簡介 (如果 description 為空則顯示預設字串)
                desc_info = album.description.strip() if (album.description and album.description.strip()) else '無簡介資訊'
        
            # 5. 標籤處理 (最多顯示前 10 個)
            tags = album.tags[:10] if album.tags else []
            tags_str = ', '.join(tags) if tags else '無'
        
            cover_url = jmcomic.JmcomicText.get_album_cover_url(album_id)
            ec = discord.Embed(
                    title=album.title,
                    description='點上面標題可直接開啟該網站',
                    url=f'https://18comic.vip/album/{album_id}/',
                    colour=discord.Color.random()
                )
            ec.add_field(name='番號:', value=album_id, inline=True)
            ec.add_field(name='作者:', value=album.author, inline=True)
            ec.add_field(name='是否為單本/單話 :', value=f" {'是 (單本/單話)' if is_single else f'否 (連載/共 {chapter_count} 章)'}", inline=False)
            if is_single:
                    ec.add_field(name='總頁數:', value=pages_info, inline=True)
            else:
                    ec.add_field(name='作品簡介:', value=desc_info, inline=False)
            ec.add_field(name='作品標籤:', value=tags_str, inline=False)
            ec.set_image(url=cover_url)
            ec.set_footer(
                    text=
                    f'{owneruser}\n祝您使用愉快'
                )
            if bot_avatar_url:
                ec.set_thumbnail(url=bot_avatar_url)
            await m.delete()
            await msg.reply(embed=ec,mention_author=False)
            
        elif "18comic.vip/photo/" in msg.content :
                
            index = msg.content.find("18comic.vip/photo/")
            bbb = msg.content[index + 18 : index + 28]
            album_id = ""
            for i in bbb:
                if i.isdigit():
                    album_id += i
                else:
                    break
            m=await msg.reply('修復漫畫連結中...',mention_author=False)        
                    
            try:
                album = client.get_album_detail(album_id)
            except:
                await msg.reply('無此漫畫 請重新檢查',mention_author=False)
                await m.delete()
                return
        
            chapter_count = len(album)
            is_single = (chapter_count <= 1)
        
            pages_info = None
            desc_info = None
        
            if is_single:
                # 單本/單話：抓取頁數資訊
                if chapter_count > 0:
                    first_photo_summary = album[0]
                    photo_detail = client.get_photo_detail(first_photo_summary.photo_id)
                    pages_info = f"{len(photo_detail)} 頁"
                else:
                    pages_info = "未知"
            else:
                # 連載作品：抓取作品簡介 (如果 description 為空則顯示預設字串)
                desc_info = album.description.strip() if (album.description and album.description.strip()) else '無簡介資訊'
        
            # 5. 標籤處理 (最多顯示前 10 個)
            tags = album.tags[:10] if album.tags else []
            tags_str = ', '.join(tags) if tags else '無'
        
            cover_url = jmcomic.JmcomicText.get_album_cover_url(album_id)
            ec = discord.Embed(
                    title=album.title,
                    description='點上面標題可直接開啟該網站',
                    url=f'https://18comic.vip/album/{album_id}/',
                    colour=discord.Color.random()
                )
            ec.add_field(name='番號:', value=album_id, inline=True)
            ec.add_field(name='作者:', value=album.author, inline=True)
            ec.add_field(name='是否為單本/單話 :', value=f" {'是 (單本/單話)' if is_single else f'否 (連載/共 {chapter_count} 章)'}", inline=False)
            if is_single:
                    ec.add_field(name='總頁數:', value=pages_info, inline=True)
            else:
                    ec.add_field(name='作品簡介:', value=desc_info, inline=False)
            ec.add_field(name='作品標籤:', value=tags_str, inline=False)
            ec.set_image(url=cover_url)
            ec.set_footer(
                    text=
                    f'{owneruser}\n祝您使用愉快'
                )
            if bot_avatar_url:
                ec.set_thumbnail(url=bot_avatar_url)
            await m.delete()
            await msg.reply(embed=ec,mention_author=False)
            
        
        elif "https://www.bilibili.com/" in msg.content :

            pattern = r"(https?://www\.bilibili\.com/video/BV[a-zA-Z0-9]+)/?"
            match1 = re.search(pattern, msg.content)
            new_url = match1.group(1).replace("www.bilibili.com", "www.vxbilibili.com")
            
            oldurl=match1.group(1).replace("www.bilibili.com", "bilibili.com")
            for i in range(3):
                sent_msg=await msg.reply(f"[bili](<{oldurl}>) • [BiliFix]({new_url})",mention_author=False)
                await asyncio.sleep(10)
                try:
                    updated_msg = await sent_msg.channel.fetch_message(sent_msg.id)
                    
                    # 4. 檢查 updated_msg.embeds 是否有資料
                    if updated_msg.embeds:
                        deletemsg=await sent_msg.reply(f"✅ 成功生成預覽！",mention_author=False)
                        try:
                            await msg.edit(suppress=True)
                        except:
                            pass
                        await asyncio.sleep(2.5)
                        await deletemsg.delete()
                        break
                    else:
                        deletemsg=await msg.reply(f"❌ Discord 未能成功生成該網址的預覽。 第({i+1}/3)次嘗試修復)",mention_author=False)
                        await asyncio.sleep(4)
                        await sent_msg.delete()
                        await deletemsg.delete()
                except discord.NotFound:
                    await msg.reply("訊息已被刪除，無法檢查是否修復成功。",mention_author=False)
                    break


        elif "https://b23.tv" in msg.content :
            pattern = r"(https?://)(b23\.tv/[a-zA-Z0-9]+)"
            match = re.search(pattern, msg.content )

            if match:
                new_url = f"{match.group(1)}vx{match.group(2)}"
            old_url=match.group(1)+match.group(2)
            for i in range(3):
                sent_msg=await msg.reply(f"[bili](<{old_url}>) • [BiliFix]({new_url})",mention_author=False)
                await asyncio.sleep(10)
                try:
                    updated_msg = await sent_msg.channel.fetch_message(sent_msg.id)
                    if updated_msg.embeds:
                        deletemsg=await sent_msg.reply(f"✅ 成功生成預覽！",mention_author=False)
                        try:
                            await msg.edit(suppress=True)
                        except:
                            pass
                        await asyncio.sleep(2.5)
                        await deletemsg.delete()
                        break
                    else:
                        deletemsg=await msg.reply(f"❌ Discord 未能成功生成該網址的預覽。 第({i+1}/3)次嘗試修復)",mention_author=False)
                        await asyncio.sleep(4)
                        await sent_msg.delete()
                        await deletemsg.delete()
                except discord.NotFound:
                    await msg.reply("訊息已被刪除，無法檢查是否修復成功。",mention_author=False)
                    break
        
        elif msg.author!=bot.user:
            if not msg.guild:
                embed=discord.Embed(title=f"有人傳送訊息給{bot.user.name},以下為信件內容",colour=discord.Color.random())
                embed.add_field(name="用戶",value=msg.author)
                embed.add_field(name="內容",value=msg.content)
                await bot.get_guild(850599773354328095).get_channel(850625850767573012).send(embed=embed)

    except Exception as e:
        # 當裡面任何一個地方報錯，程式會直接跳到這裡！
        
        # 1. 取得詳細的錯誤堆疊
        tb_msg = "".join(
            traceback.format_exception(type(e), e, e.__traceback__)
        )
        if len(tb_msg) > 1900:
            tb_msg = tb_msg[:1900] + "\n... (訊息過長已截斷)"
            
        # 2. 發送到你的日誌頻道
        channel_id = 1533491542113779865
        channel = bot.get_channel(channel_id)
        if channel:
            try:
                await channel.send(f"```python\n[on_message Global Error]\n{tb_msg}\n```")
            except Exception as send_err:
                print(f"發送錯誤日誌失敗: {send_err}")
        else:
            print(f"警告：找不到錯誤日誌頻道 (ID: {channel_id})")
            
        # 3. 可以在終端機印出來（保留原本的紅字方便看）
        raise e
    
    txtcontent=["marvel","vel","媽","mar","女馬","漫威","曼威"]
    cleancontect=re.sub(r'\s+', '', msg.content)
    if int(msg.author.id) != 613578839372857383 and int(msg.author.id) != 589092386182004755 and ":emoji_128:" in msg.content:
        await msg.delete()
    elif int(msg.author.id) != 613578839372857383 and int(msg.author.id) != 589092386182004755 and any(kw in msg.content.lower() for kw in txtcontent):
        await msg.delete()
    elif int(msg.author.id) != 613578839372857383 and int(msg.author.id) != 589092386182004755 and any(kw in cleancontect.lower() for kw in txtcontent):
        await msg.delete()


    await bot.process_commands(msg)   
    #防止on message跟command衝突    

 

@bot.event
async def on_command_error(ctx,error):
    if hasattr(ctx.command,"on_error"):
        return
    if isinstance(error,commands.errors.MissingRequiredArgument):
        await ctx.send("沒有給參數")
    elif isinstance(error,commands.errors.MissingPermissions):
        await ctx.send("沒有權限")  
    elif isinstance(error,commands.CommandOnCooldown):
        await ctx.send(f'冷卻中啦,{error.retry_after:.2f}秒')
    elif isinstance(error,commands.MaxConcurrencyReached):
        await ctx.send('此命令設有可同時使用次數限制') 
    elif  isinstance(error,commands.errors.CommandNotFound):
            pass          
    else:
            tb_msg = "".join(
                    traceback.format_exception(
                        type(error), error, error.__traceback__
                    )
                )
                # 防範訊息超過 Discord 2000 字元限制
            if len(tb_msg) > 1900:
                tb_msg = tb_msg[:1900] + "\n... (訊息過長已截斷)"
            await bot.get_channel(1533491542113779865).send(f"```python\n{tb_msg}\n```")
            raise error     


@bot.command()
@commands.is_owner()
async def sev(ctx):
    em = discord.Embed(title="伺服器狀態", color=discord.Color.random())
    em.add_field(name="伺服器名稱", value=ctx.guild.name)
    em.add_field(name="伺服器創建時間", value=ctx.guild.created_at.strftime("%Y年%m月%d日"), inline=False)
    em.add_field(name="成員數", value=ctx.guild.member_count, inline=True)  # 建議用 member_count 比較安全
    em.add_field(name="頻道數量", value=len(ctx.guild.channels), inline=True)
    em.add_field(name="身分組數量", value=len(ctx.guild.roles), inline=True)  
    
    # 修復圖示 URL 抓取方式
    if ctx.guild.icon:
        em.set_thumbnail(url=ctx.guild.icon.url)
        
    em.set_footer(text="查詢系統")
    await ctx.send(embed=em)
    
    ccc = []
    for namea in ctx.guild.roles:
        ccc.append(namea.name)   
        
    # 將串列轉成字串，避免型態錯誤
    roles_str = ", ".join(ccc)
    if len(roles_str) > 4000:  # 防止身分組太多超過 Discord 限制
        roles_str = roles_str[:4000] + "... (過長已截斷)"
        
    asa = discord.Embed(title="身分組", description=roles_str, color=discord.Color.random())
    await ctx.send(embed=asa)



@bot.command()
@commands.is_owner()
async def players(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(color=discord.Color.random())
    
    # 修正大頭貼 URL 抓取方式（若使用者沒設大頭貼會改抓預設頭貼）
    avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
    
    embed.set_author(name=member, icon_url=avatar_url)
    embed.set_thumbnail(url=avatar_url)
    embed.add_field(name=":computer:帳號創建時間", value=member.created_at.strftime("%Y年%m月%d日"), inline=True)            
    embed.add_field(name=":calling:加入伺服器時間", value=member.joined_at.strftime("%Y年%m月%d日") if member.joined_at else "未知", inline=True)            
    since = member.premium_since
    embed.add_field(name=":gem:加成伺服器時間", value=since.strftime("%Y年%m月%d日") if since else "無加成", inline=True)               
    embed.add_field(name="是否為bot", value="是" if member.bot else "否", inline=True)
    embed.add_field(name="目前狀態", value=str(member.status), inline=True) 
    embed.add_field(name="最高權限身分組", value=member.top_role.mention)   
    embed.set_footer(text='查詢系統')
    await ctx.send(embed=embed)


class GuildPaginationView(discord.ui.View):
    def __init__(self, guilds, per_page=2):
        super().__init__(timeout=180) # 3分鐘沒點擊按鈕就會失效
        self.guilds = guilds
        self.per_page = per_page
        self.current_page = 0
        self.max_pages = (len(guilds) - 1) // per_page + 1
        self.update_buttons()

    def update_buttons(self):
        # 當前在第一頁時，禁用「上一頁」
        self.prev_button.disabled = self.current_page == 0
        # 當前在最後一頁時，禁用「下一頁」
        self.next_button.disabled = self.current_page >= self.max_pages - 1

    def create_embed(self):
        embed = discord.Embed(
            title=f"🤖 機器人所在的伺服器列表 (共 {len(self.guilds)} 個)",
            color=discord.Color.blue()
        )
        
        # 計算當前頁面要顯示的切片範圍
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_guilds = self.guilds[start:end]

        for guild in page_guilds:
            info = f"👥 成員數：`{guild.member_count}` 人\n👑 擁有者：`{guild.owner}`"
            embed.add_field(name=f"🏠 {guild.name}", value=info, inline=False)
            
        embed.set_footer(text=f"第 {self.current_page + 1} 頁 / 共 {self.max_pages} 頁")
        return embed

    # 上一頁按鈕
    @discord.ui.button(label="◀️ 上一頁", style=discord.ButtonStyle.primary, custom_id="prev_page")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()

    # 下一頁按鈕
    @discord.ui.button(label="下一頁 ▶️", style=discord.ButtonStyle.primary, custom_id="next_page")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()


# 2. 伺服器列表查詢指令
@bot.command()
@commands.is_owner()
async def bot_guilds(ctx):
    guilds = bot.guilds
    if not guilds:
        await ctx.send("目前機器人尚未加入任何伺服器。")
        return

    # 建立 View 實例（測試用 per_page=2，正式上線時可以改成 10）
    view = GuildPaginationView(guilds, per_page=10)
    
    # 發送第一頁的訊息與按鈕
    await ctx.send(embed=view.create_embed(), view=view)



@bot.command()
@commands.is_owner()
async def www(ctx,member:discord.Member,*,mes):  
    await ctx.message.delete()  
    await member.send(mes)
    c=await ctx.send("訊息已發送")
    await asyncio.sleep(5)
    await c.delete()   



@bot.command()
async def n(ctx,bbb=None):
    if bbb==None:
        await ctx.send('你沒有給我番號,我將隨機生成')
        while True:
            bbb=random.randint(100000,999999)
            print(bbb)   
            try:
                req=requests.get(f'https://nhentai.net/g/{bbb}/')
                soup=BeautifulSoup(req.text,features='lxml')
                imgs=soup.select('img')[2]
                app=imgs['src']
                title=soup.select('span')
                break
            except:
                continue
    else:
        try:
                req=requests.get(f'https://nhentai.net/g/{bbb}/')
                soup=BeautifulSoup(req.text,features='lxml')
                imgs=soup.select('img')[2]
                app=imgs['src']
                title=soup.select('span')
        except:
                await ctx.send('搜尋失敗')        
    title3=[]
    asa=[]
    asa2=[]
    lan=[]
    for title2 in title:
        try:
            if title2['class']==['pretty']:
                title3.append(str(title2).split('>')[1].split('<')[0])
                break
        except:
            continue
    for title2 in title:
        try:
            if title2['class']==['name']:
                asa.append(title2)
                continue
        except:
            continue
    for title2 in title:
        try:
            if title2['class']==['after']:
                lan.append(str(title2).split('[')[1].split(']')[0])
                break
        except:
            lan.append('None')       
    try:
        asa2.append(str(asa[-1]).split('>')[1].split('<')[0])
    except:
        await ctx.send('搜不到')
        return
    ec=discord.Embed(title=f':link:{title3[0]}',description='點上面標題可直接到網站',url=f'https://nhentai.net/g/{bbb}/',colour=discord.Color.random())
    ec.add_field(name='ℹ️番號:',value=bbb)
    ec.add_field(name=':speech_balloon:語言:',value=lan[0])
    ec.add_field(name=':book:頁數:',value=asa2[0])
    ec.add_field(name='封面圖',value='⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️',inline=False)
    ec.set_image(url=app)
    ec.set_thumbnail(url='https://i.imgur.com/uLAimaY.png')
    ec.set_footer(text='語言僅供參考,未必準確,None表示沒抓到')
    await ctx.send(embed=ec)     



@bot.command()
async def h(ctx, bbb=None):
    if bbb is None:
        await ctx.send('沒有給我番號')
        
    # 抓取指定番號頁面
    try:
        res = requests.get(f'https://www.wn07.cfd/photos-index-aid-{bbb}.html', timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, features='lxml')
    except Exception:
        await ctx.send('搜尋不到該番號或網站無法連線。')
        return  

    # 安全地解析元素
    imgs = soup.select('img')
    if len(imgs) < 6:
        await ctx.send('頁面解析失敗（圖片數量不足或番號不存在）。')
        return

    title = imgs[2].get('alt', '無標題')
    image = imgs[2].get('src', '')

    # 解析頁數
    labels = soup.select('label')
    page_count = '未知'
    if len(labels) > 1 and '：' in labels[1].text:
        page_count = labels[1].text.split('：')[1].split('P')[0]

    # 建立 Embed
    ec = discord.Embed(
        title=title,
        description='點上面標題可直接到網站',
        url=f'https://www.wnacg.org/photos-index-aid-{bbb}.html',
        colour=discord.Color.random()
    )
    ec.add_field(name='番號:', value=bbb, inline=True)
    ec.add_field(name='頁數:', value=page_count, inline=True)
    
    if image:
        # 避免重複拼接 https:
        img_url = image if image.startswith('http') else f'https:{image[2:]}'
        ec.set_image(url=img_url)

    await ctx.send(embed=ec)


class BlackjackView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # 如果希望按鈕永久有效（機器人重啟也能用），設定 timeout=None

    # 參與遊戲按鈕 (綠色 Success 風格 + 勾勾 Emoji)
    @discord.ui.button(label='參與遊戲', style=discord.ButtonStyle.success, emoji='✅', custom_id='join_game_btn')
    async def join_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 這裡寫點擊「參與遊戲」後的邏輯
        await interaction.response.send_message(f"@{interaction.user.name} 成功參與遊戲！", ephemeral=True)

    # 開始遊戲按鈕 (灰色 Secondary 風格 + 橘色/黃色方塊 Emoji)
    @discord.ui.button(label='開始遊戲', style=discord.ButtonStyle.secondary, emoji='🟧', custom_id='start_game_btn')
    async def start_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 這裡寫點擊「開始遊戲」後的邏輯
        await interaction.response.send_message("遊戲即將開始！", ephemeral=True)



@bot.command(name='testbtn')
@commands.is_owner()
async def testbtn(ctx):
    # 取得機器人頭貼作為縮圖
    bot_avatar_url = bot.user.display_avatar.url if bot.user else ""

    # 建立 Embed 效果
    ec = discord.Embed(
        title="多人 21 點",
        description="運氣與策略的完美結合\n\n目標是讓手牌點數盡量接近 21 點但不超過。多人同桌競技，和朋友較量運氣與判斷力，看誰最先達到完美點數",
        colour=discord.Color.from_rgb(40, 40, 45)
    )
    
    if bot_avatar_url:
        ec.set_thumbnail(url=bot_avatar_url)

    # 帶入之前寫好的按鈕 View
    my_view = BlackjackView()

    # 發送訊息
    await ctx.send(embed=ec, view=my_view)

@bot.tree.command(name="testbtn", description="發送多人21點測試按鈕")
@commands.is_owner()
async def testbtn(interaction: discord.Interaction):
    # 取得機器人頭貼作為縮圖
    bot_avatar_url = bot.user.display_avatar.url if bot.user else ""

    # 建立 Embed 效果
    ec = discord.Embed(
        title="多人 21 點",
        description="運氣與策略的完美結合\n\n目標是讓手牌點數盡量接近 21 點但不超過。多人同桌競技，和朋友較量運氣與判斷力，看誰最先達到完美點數",
        colour=discord.Color.from_rgb(40, 40, 45)
    )
    
    if bot_avatar_url:
        ec.set_thumbnail(url=bot_avatar_url)

    # 帶入按鈕 View
    my_view = BlackjackView()

    # 因為是 Interaction，必須透過 response.send_message 發送
    await interaction.response.send_message(embed=ec, view=my_view)

from typing import Optional
from discord import app_commands

@bot.hybrid_command(name="reload", description="重新載入指定的 Cog 模組，不填則重載全部 (僅限擁有者)")
@commands.is_owner()
@app_commands.describe(extension="要重新載入的檔案名稱 (若不填，則預設重載全部已載入的模組)")
async def reload(ctx: commands.Context, extension: Optional[str] = None):
    try:
        # 同步 Slash 指令
        synced = await bot.tree.sync()

        if extension:
            # 1. 如果有指定特定的模組名稱
            await bot.reload_extension(extension)
            await ctx.send(f"✅ 成功重新載入模組：`{extension}`！已同步 {len(synced)} 個 Slash 指令。")
        else:
            # 2. 如果沒有給檔案名，自動抓取全部已載入的模組進行重載
            if not bot.extensions:
                await ctx.send("⚠️ 目前沒有任何已載入的模組。")
                return

            reloaded_list = []
            # 複製一份 keys 避免在迭代時動態修改字典報錯
            for ext in list(bot.extensions.keys()):
                await bot.reload_extension(ext)
                reloaded_list.append(ext)

            modules_str = ", ".join([f"`{e}`" for e in reloaded_list])
            await ctx.send(f"✅ 成功重新載入**全部**共 {len(reloaded_list)} 個模組：\n{modules_str}\n已同步 {len(synced)} 個 Slash 指令。")

    except Exception as e:
        await ctx.send(f"❌ 重新載入失敗：\n```py\n{e}\n```")

@bot.command()
async def help(ctx, help=None):
    tell=r'https://telegra.ph/xxxxxx(xxx通常會為一大串 直接貼上即可)'
    comicc=r'https://18comic.vip/album/1427038/xxxxx(xxx通常會為一大串 直接貼上即可)'

    ec = discord.Embed(title='📋歡迎來到說明書📋',
                                description=f'🔺指令前綴:`.`',
                                colour=discord.Color.random())
    ec.add_field(
        name='主要功能:修復h漫畫連結',
        value=f'```用法是直接貼連結即可 不須前綴和指令 目前支援網站:紳士漫畫,telegram漫畫,禁漫天堂，範例:\nhttps://www.wnacg.com/photos-index-aid-374687.html \n{tell}\n{comicc}```'
        ,inline=False)
    ec.add_field(
        name='指令:``.h``',
        value='```.h空一格加上番號 範例:.h 374687```'
        ,inline=False
    )
    ec.add_field(
            name='指令:``.tel``',
            value=f'```.tel空一格加上整個網址\n範例:\n.tel {tell}```'
            ,inline=False
        )
    ec.set_thumbnail(url=bot.user.avatar.url)
    ec.set_image(url='https://media.discordapp.net/attachments/854736687002943488/891300310461587506/Tw.gif')
    ec.set_footer(
        text=
        f'作者關心您{owneruser}'
    )
    await ctx.send(embed=ec)


async def main():
    await run_web_server()
    token = os.getenv("DISCORD_TOKEN")
    await bot.start(token)


if __name__ == '__main__':

    
    asyncio.run(main())
