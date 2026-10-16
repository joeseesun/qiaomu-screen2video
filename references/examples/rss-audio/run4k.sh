set -e
cd $WORK
FF=/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg
cvenv/bin/python render_plate4k.py
python3 -I build13.py A 1.4 | tail -1
python3 -I build13.py B 1.4 | tail -1
D="$PROJECT/成片"; C="$D/封面.png"
$FF -y -v error -loop 1 -framerate 30 -t 0.5 -i "$C" -f lavfi -t 0.5 -i anullsrc=r=44100:cl=stereo -vf "scale=3840:2160:flags=lanczos,setsar=1,format=yuv420p" -c:v libx264 -preset medium -crf 17 -profile:v high -level 5.1 -pix_fmt yuv420p -c:a aac -b:a 192k -ar 44100 -ac 2 -shortest cover4k.mp4
declare -A N=( [A]=带搜索引导片尾 [B]=无引导片尾 )
for v in A B; do
  printf "file 'cover4k.mp4'\nfile 'final4k_$v.mp4'\n" > list_$v.txt
  $FF -y -v error -f concat -safe 0 -i list_$v.txt -i "$C" -map 0 -map 1 -c copy -c:v:1 png -disposition:v:1 attached_pic -movflags +faststart "$D/v11_4K_${v}_${N[$v]}_中英双语_含封面.mp4"
  echo done $v
done
echo ALLDONE
