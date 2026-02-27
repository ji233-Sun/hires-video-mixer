import os
import sys
import shutil
import subprocess
import uuid
import webbrowser
import threading

from flask import Flask, render_template, request, send_file, jsonify

# 确定基础路径（兼容 PyInstaller 打包）
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    TEMPLATE_DIR = os.path.join(sys._MEIPASS, 'templates')
    STATIC_DIR = os.path.join(sys._MEIPASS, 'static')
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
    STATIC_DIR = os.path.join(BASE_DIR, 'static')

UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
OUTPUT_DIR = os.path.join(BASE_DIR, 'outputs')

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 * 1024  # 10GB


def get_ffmpeg_path():
    """获取 FFmpeg 路径，打包时优先使用内置的"""
    if getattr(sys, 'frozen', False):
        # 打包模式：检查程序同目录下的 ffmpeg
        if sys.platform == 'win32':
            bundled = os.path.join(BASE_DIR, 'ffmpeg', 'ffmpeg.exe')
        else:
            bundled = os.path.join(BASE_DIR, 'ffmpeg', 'ffmpeg')
        if os.path.isfile(bundled):
            return bundled
    # 回退到系统 PATH
    return 'ffmpeg'


def get_ffprobe_path():
    """获取 FFprobe 路径"""
    if getattr(sys, 'frozen', False):
        if sys.platform == 'win32':
            bundled = os.path.join(BASE_DIR, 'ffmpeg', 'ffprobe.exe')
        else:
            bundled = os.path.join(BASE_DIR, 'ffmpeg', 'ffprobe')
        if os.path.isfile(bundled):
            return bundled
    return 'ffprobe'


def clean_dirs():
    """启动时清理 uploads 和 outputs 目录"""
    for d in [UPLOAD_DIR, OUTPUT_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)


# FLAC 质量预设
QUALITY_PRESETS = {
    '24bit-48khz': {'sample_fmt': 's32', 'ar': '48000', 'label': '24bit / 48kHz'},
    '24bit-96khz': {'sample_fmt': 's32', 'ar': '96000', 'label': '24bit / 96kHz'},
    '24bit-192khz': {'sample_fmt': 's32', 'ar': '192000', 'label': '24bit / 192kHz'},
}


@app.route('/')
def index():
    return render_template('index.html', presets=QUALITY_PRESETS)


@app.route('/process', methods=['POST'])
def process():
    audio_file = request.files.get('audio')
    video_file = request.files.get('video')

    if not audio_file or not video_file:
        return jsonify({'error': '请同时上传音频和视频文件'}), 400

    quality = request.form.get('quality', '24bit-48khz')
    if quality not in QUALITY_PRESETS:
        return jsonify({'error': '无效的质量选项'}), 400

    preset = QUALITY_PRESETS[quality]
    task_id = uuid.uuid4().hex[:8]

    # 保存上传文件
    audio_ext = os.path.splitext(audio_file.filename)[1] or '.audio'
    video_ext = os.path.splitext(video_file.filename)[1] or '.video'
    audio_path = os.path.join(UPLOAD_DIR, f'{task_id}_audio{audio_ext}')
    video_path = os.path.join(UPLOAD_DIR, f'{task_id}_video{video_ext}')
    audio_file.save(audio_path)
    video_file.save(video_path)

    # 中间 FLAC 文件
    flac_path = os.path.join(UPLOAD_DIR, f'{task_id}_audio.flac')
    # 输出 MKV
    output_name = f'{os.path.splitext(video_file.filename)[0]}_hires.mkv'
    output_path = os.path.join(OUTPUT_DIR, f'{task_id}_{output_name}')

    ffmpeg = get_ffmpeg_path()

    try:
        # 步骤1：音频转 FLAC
        cmd_flac = [
            ffmpeg, '-y', '-i', audio_path,
            '-c:a', 'flac',
            '-sample_fmt', preset['sample_fmt'],
            '-ar', preset['ar'],
            flac_path
        ]
        result = subprocess.run(cmd_flac, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            return jsonify({'error': f'音频转换失败: {result.stderr[-500:]}'}), 500

        # 步骤2：替换视频音轨，输出 MKV
        cmd_mux = [
            ffmpeg, '-y',
            '-i', video_path,
            '-i', flac_path,
            '-c:v', 'copy',
            '-c:a', 'copy',
            '-map', '0:v:0',
            '-map', '1:a:0',
            output_path
        ]
        result = subprocess.run(cmd_mux, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            return jsonify({'error': f'视频合成失败: {result.stderr[-500:]}'}), 500

        # 获取输出文件大小
        file_size = os.path.getsize(output_path)

        return jsonify({
            'success': True,
            'task_id': task_id,
            'filename': output_name,
            'size': file_size,
        })

    except subprocess.TimeoutExpired:
        return jsonify({'error': '处理超时（10分钟限制）'}), 500
    except Exception as e:
        return jsonify({'error': f'处理失败: {str(e)}'}), 500
    finally:
        # 清理中间文件
        for f in [audio_path, video_path, flac_path]:
            if os.path.exists(f):
                os.remove(f)


@app.route('/download/<task_id>/<filename>')
def download(task_id, filename):
    # 安全检查：防止路径穿越
    safe_name = os.path.basename(filename)
    file_path = os.path.join(OUTPUT_DIR, f'{task_id}_{safe_name}')
    if not os.path.isfile(file_path):
        return jsonify({'error': '文件不存在或已过期'}), 404
    return send_file(file_path, as_attachment=True, download_name=safe_name)


@app.route('/check-ffmpeg')
def check_ffmpeg():
    """检查 FFmpeg 是否可用"""
    try:
        ffmpeg = get_ffmpeg_path()
        result = subprocess.run([ffmpeg, '-version'], capture_output=True, text=True, timeout=5)
        version_line = result.stdout.split('\n')[0] if result.stdout else 'unknown'
        return jsonify({'available': True, 'version': version_line})
    except Exception:
        return jsonify({'available': False, 'version': None})


def open_browser():
    webbrowser.open('http://127.0.0.1:5000')


if __name__ == '__main__':
    clean_dirs()
    # 延迟打开浏览器
    threading.Timer(1.0, open_browser).start()
    app.run(host='127.0.0.1', port=5000, debug=False)
