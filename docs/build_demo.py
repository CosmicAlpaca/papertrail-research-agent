"""Narrated walkthrough assembled from actual browser captures; search waits omitted.

Requires Windows System.Speech, captured frames under work/, imageio-ffmpeg.
This is an edited screen walkthrough, not an unedited continuous recording.
"""
import json
import shutil
import subprocess
import wave
from pathlib import Path
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'work/demo';WORK.mkdir(exist_ok=True)
scenes=[
('live-home.jpg','01 / PaperTrail - evidence-led discovery',
 'This is PaperTrail, a new research application built around OpenAlex. The aim is to make complex literature searches easier to inspect, rather than promise that an AI always finds the best papers. You describe a research question, review its requirements, and follow the source evidence behind the results. These are captures from the actual deployed application. This walkthrough is edited, with search waits omitted. The code and the report include the measured failures as well as successful examples.'),
('live-plan.jpg','02 / Review the search before running it',
 'This example asks for graph neural network explanation methods from twenty eighteen through twenty twenty four, evaluated on real graphs rather than only synthetic data. Gemini converts the question into retrieval phrases and explicit criteria. The user can edit the queries, dates, access filter, and search depth. The plan is a proposal, not a hidden interpretation. Diligent search adds citation exploration and at most one repair round. A fixed external call budget keeps the search bounded.'),
('live-evidence.jpg','03 / Inspect the source behind a match',
 'The result list comes from real OpenAlex records. Keyword and semantic retrieval supply candidates, and a local, quantized GTE Modern BERT model reranks them on the CPU. Here PGM Explainer and GNN Explainer have source evidence for the reviewed requirements. Selecting a paper opens its evidence panel. Supported judgments require an exact quote that the server can find in the supplied title or abstract. This verifies attribution. It does not prove that the model interpreted the quote correctly.'),
('live-matrix.jpg','04 / Compare criteria across the reading list',
 'The matrix makes uncertainty visible across papers. Supported, contradicted, and uncertain are different states. A paper is not rejected simply because its abstract omits a detail. In development, the model incorrectly treated a wide range of datasets as evidence of real datasets. That failure led to stricter assessment instructions. The interface also distinguishes papers outside the evidence assessment. Only up to fifteen retrieved candidates are assessed before the final ordering, and full papers have not been read.'),
('live-citations.jpg','05 / Follow actual citation links',
 'The citation view uses actual OpenAlex reference links between returned papers. These edges are bibliographic relationships. They do not mean that papers agree, that a method is better, or that an AI has verified the whole research field. Citation exploration can surface useful older work, while publication years and access restrictions are checked again. If the available evidence leaves a requirement uncovered, the agent can issue one targeted repair search and preserve any remaining gap.'),
('live-chat.jpg','06 / Ask a grounded follow-up question',
 'The reading list also supports follow-up questions. The application selects relevant returned papers for the question and sends their available metadata to the hosted model. Each displayed factual item must reference an existing result and include a source quote that passes the matching check. A focused question about PGM Explainer can ask what it proposes and whether real-world evaluation is stated. The answer stays within the abstracts. If the sources do not establish a point, the system should leave that point unresolved.'),
('live-trace.jpg','07 / Keep the research trail',
 'The search trail records actions, queries, citation exploration, provider usage and assessment progress. It is an audit of what happened, not a display of hidden model reasoning. Papers and evidence can be exported as JSON, CSV or BibTeX. A private workspace key controls access to saved investigations. PostgreSQL belongs to the user in a separate Railway project. Model credentials remain on the server. The primary analysis model has a configured fallback, and provider failures remain visible in saved results.'),
('report-pages/page-5.png','08 / Evaluate the improvement honestly',
 'The report compares live Asta and Google Scholar workflows and includes an eight-query development pilot drawn from LitSearch. Scholar won the observed remembered-paper example. The initial small reranker also lost some correct targets. On the same cached candidate pools, the upgraded int8 model improved target hit at ten from thirty seven point five percent to fifty percent, and reciprocal rank from point three one three to point four three eight. This is development evidence, not an independent overall win. Broader blind human evaluation and full-text checking remain future work.')
]
items=[]
for i,(source,title,narration) in enumerate(scenes,1):
    src=ROOT/'work'/source
    if not src.exists():raise FileNotFoundError(src)
    image=WORK/f'scene-{i}{src.suffix}';shutil.copy2(src,image)
    (WORK/f'scene-{i}.txt').write_text(title,encoding='utf8')
    items.append({'image':image.name,'audio':str(WORK/f'scene-{i}.wav'),'text':narration})
(WORK/'narration.json').write_text(json.dumps(items),encoding='utf8')
ps=r'''Add-Type -AssemblyName System.Speech
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$english = $voice.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -eq 'en-US' } | Select-Object -First 1
if ($english) { $voice.SelectVoice($english.VoiceInfo.Name) }
$voice.Rate = 0
$items = Get-Content -LiteralPath $PSScriptRoot\narration.json -Raw | ConvertFrom-Json
foreach ($item in $items) {
  $voice.SetOutputToWaveFile($item.audio)
  $voice.Speak($item.text)
  $voice.SetOutputToNull()
}
$voice.Dispose()
'''
(WORK/'narrate.ps1').write_text(ps,encoding='utf8')
subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',str(WORK/'narrate.ps1')],check=True,creationflags=0x08000000)
shutil.copy2('C:/Windows/Fonts/arial.ttf',WORK/'font.ttf')
ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
duration=0
for i,item in enumerate(items,1):
    with wave.open(item['audio']) as audio:seconds=audio.getnframes()/audio.getframerate()+1.5
    duration+=seconds
    vf=f'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:800:(ow-iw)/2:0:color=0xf7f8f2,drawtext=fontfile=font.ttf:textfile=scene-{i}.txt:fontcolor=0x173f36:fontsize=23:x=32:y=748'
    command=[ffmpeg,'-hide_banner','-loglevel','error','-y','-loop','1','-i',item['image'],'-i',item['audio'],'-vf',vf,'-af','apad=pad_dur=1.5','-t',str(seconds),'-r','10','-c:v','libx264','-preset','fast','-tune','stillimage','-pix_fmt','yuv420p','-c:a','aac','-b:a','112k','-movflags','+faststart',f'part-{i}.mp4']
    subprocess.run(command,cwd=WORK,check=True)
    print('Encoded scene',i,round(seconds,1),'seconds',flush=True)
(WORK/'concat.txt').write_text('\n'.join(f"file 'part-{i}.mp4'" for i in range(1,len(items)+1)),encoding='utf8')
output=ROOT/'outputs/PaperTrail-Narrated-Walkthrough.mp4'
subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i','concat.txt','-c','copy','-movflags','+faststart',str(output)],cwd=WORK,check=True)
if duration>300:raise RuntimeError(f'Walkthrough exceeds five minutes: {duration}')
print('Total seconds:',round(duration,1),'Output:',output)
