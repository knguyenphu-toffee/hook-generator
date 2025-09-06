import os
import requests
import json
import time
import jwt
import random
from pathlib import Path
from tqdm import tqdm
import sys
import subprocess
import shutil

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# === Configuration ===
# IMPORTANT: Store these in environment variables or a secure config file!
KLING_ACCESS_KEY = os.getenv("KLING_ACCESS_KEY", "your-access-key-here")
KLING_SECRET_KEY = os.getenv("KLING_SECRET_KEY", "your-secret-key-here")

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

BASE_IMAGE_DIR = os.path.join(SCRIPT_DIR, "base-image")
OUTPUT_VIDEOS_DIR = os.path.join(SCRIPT_DIR, "output-videos")
TEMP_DIR = os.path.join(SCRIPT_DIR, "temp_kling_videos")

# Ensure output directories exist
os.makedirs(OUTPUT_VIDEOS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(BASE_IMAGE_DIR, exist_ok=True)

# Video prompts for different emotions
PROMPTS = {
    "surprised": "Animate the person in the image reacting with subtle shocked surprise. Their eyes widen, eyebrows lift sharply, and their mouth opens slightly in shock. The motion should feel natural and quick, like they've just seen something unexpected. Maintain the original framing — if the person's arm is extended under the camera, keep it consistent as a selfie, otherwise keep it as a front-facing UGC style shot. No changes to the background or setting. Do not remove or change the position of the arm or hand holding the phone underneath the camera — preserve it exactly as in the base image. Add very subtle, natural handheld camera sway and pivot, as if the phone is being held in the person's hand, so the framing feels like a real TikTok selfie.",
    "sad": "Animate the person in the image reacting with subtle sadness. Their eyes soften and grow slightly glassy, eyelids lowering as if weighed down. Their eyebrows angle upward in the middle, creating a vulnerable, sorrowful expression. A small downward tilt of the head or shoulders adds to the feeling of heaviness. The motion should feel natural and tender, like they've just been hit with an emotional thought. Maintain the original framing — if the person's arm is extended under the camera, keep it consistent as a selfie, otherwise keep it as a front-facing UGC style shot. Do not remove or change the position of the arm or hand holding the phone underneath the camera — preserve it exactly as in the base image. Add very subtle, natural handheld camera sway and pivot, as if the phone is being held in the person's hand, so the framing feels like a real TikTok selfie.",
    "confused": "Animate the person in the image reacting with visible confusion while keeping their gaze locked directly at the camera. Their eyebrows knit together and raise unevenly, their eyes narrow slightly with puzzlement, and their mouth shifts into a subtle frown or half-open, questioning expression. A small head tilt or slight micro-shake emphasizes the confusion, but their eyes never leave the lens, as if they're baffled by the viewer or what they're seeing on screen. The motion should feel natural, quick, and clearly readable. Maintain the original framing — if the person's arm is extended under the camera, keep it consistent as a selfie, otherwise keep it as a front-facing UGC style shot. Do not remove or change the position of the arm or hand holding the phone underneath the camera — preserve it exactly as in the base image. Add very subtle, natural handheld camera sway and pivot, as if the phone is being held in the person's hand, so the framing feels like a real TikTok selfie.",
    "romantic": "Animate the person in the image reacting with a shy, romantic expression, as if they've just felt butterflies in their stomach. Their eyes glance down briefly, then lift back up with a soft, lingering gaze full of affection. A gentle blush appears across their cheeks, and their lips curl into a nervous but sweet smile that wavers slightly, as if they can't hide their feelings. Their head tilts down or to the side in a bashful way, adding to the sense of vulnerability. The motion should feel natural, tender, and slightly flustered, as if they're caught in an unexpected romantic moment. Maintain the original framing — if the person's arm is extended under the camera, keep it consistent as a selfie, otherwise keep it as a front-facing UGC style shot. Do not remove or change the position of the arm or hand holding the phone underneath the camera — preserve it exactly as in the base image. Add very subtle, natural handheld camera sway and pivot, as if the phone is being held in the person's hand, so the framing feels like a real TikTok selfie.",
    "crying": "Animate the person in the image beginning to cry with genuine emotion. Their eyes well up with tears that glisten and start to fall down their cheeks. Their eyebrows draw together in anguish, their lower lip trembles slightly, and their breathing becomes shaky and uneven. Their face contorts with raw emotion as they try to hold back sobs. The motion should feel deeply emotional and authentic, like they're experiencing overwhelming sadness or pain. Maintain the original framing — if the person's arm is extended under the camera, keep it consistent as a selfie, otherwise keep it as a front-facing UGC style shot. Do not remove or change the position of the arm or hand holding the phone underneath the camera — preserve it exactly as in the base image. Add very subtle, natural handheld camera sway and pivot, as if the phone is being held in the person's hand, so the framing feels like a real TikTok selfie."
}

def check_ffmpeg():
    """Check if FFmpeg is available on the system."""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def crop_video_to_9_16(input_path, progress_bar=None):
    """
    Crop video from 16:9 to 9:16 aspect ratio using FFmpeg.
    Replaces the original file with the cropped version.
    """
    if not check_ffmpeg():
        if progress_bar:
            progress_bar.set_description("FFmpeg not available - skipping crop")
        return False
    
    try:
        if progress_bar:
            progress_bar.set_description(f"Cropping {os.path.basename(input_path)}")
        
        # Create temporary output file
        temp_output = input_path.replace('.mp4', '_temp_cropped.mp4')
        
        # FFmpeg command to crop to 9:16 (centered crop)
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-vf', 'crop=ih*9/16:ih',  # Crop to 9:16, centered
            '-c:a', 'copy',  # Copy audio without re-encoding
            '-y',  # Overwrite output file
            temp_output
        ]
        
        # Run FFmpeg with suppressed output
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Replace original file with cropped version
            shutil.move(temp_output, input_path)
            if progress_bar:
                progress_bar.set_description(f"Cropped {os.path.basename(input_path)}")
            return True
        else:
            # Clean up temp file if it exists
            if os.path.exists(temp_output):
                os.remove(temp_output)
            if progress_bar:
                progress_bar.set_description(f"Crop failed: {os.path.basename(input_path)}")
            return False
            
    except Exception as e:
        # Clean up temp file if it exists
        temp_output = input_path.replace('.mp4', '_temp_cropped.mp4')
        if os.path.exists(temp_output):
            os.remove(temp_output)
        if progress_bar:
            progress_bar.set_description(f"Crop error: {str(e)[:30]}")
        return False

def crop_all_generated_videos(successful_videos, progress_bar=None):
    """
    Crop all successfully generated videos to 9:16 aspect ratio.
    """
    if not successful_videos:
        return 0, 0
    
    if not check_ffmpeg():
        print("\n⚠️ FFmpeg not available - skipping video cropping")
        return 0, len(successful_videos)
    
    print(f"\n🎬 Cropping {len(successful_videos)} videos to 9:16 aspect ratio...")
    
    cropped_successfully = 0
    crop_failed = 0
    
    # Create sub-progress bar for cropping
    with tqdm(total=len(successful_videos), desc="Cropping videos", leave=False,
              bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}]') as crop_progress:
        
        for video_path in successful_videos:
            if crop_video_to_9_16(video_path, crop_progress):
                cropped_successfully += 1
            else:
                crop_failed += 1
            crop_progress.update(1)
    
    return cropped_successfully, crop_failed

def encode_jwt_token(ak, sk):
    """Generate JWT token for Kling AI authentication - EXACT method from Kling docs."""
    headers = {
        "alg": "HS256",
        "typ": "JWT"
    }
    payload = {
        "iss": ak,
        "exp": int(time.time()) + 1800,  # Valid for 30 minutes
        "nbf": int(time.time()) - 5  # Valid from 5 seconds ago
    }
    token = jwt.encode(payload, sk, headers=headers)
    return token

def upload_image_to_temporary_hosting(image_path, progress_bar=None):
    """
    Upload a local image to get a public URL.
    Using tmpfiles.org for temporary file hosting (no API key required).
    """
    try:
        if progress_bar:
            progress_bar.set_description("Uploading image")
        
        # Use tmpfiles.org - reliable and free
        with open(image_path, 'rb') as f:
            files = {'file': f}
            response = requests.post('https://tmpfiles.org/api/v1/upload', files=files)
            
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                # Convert the URL to direct link format
                url = data['data']['url'].replace('tmpfiles.org/', 'tmpfiles.org/dl/')
                return url
                
    except Exception as e:
        if progress_bar:
            progress_bar.set_description(f"Upload failed: {str(e)[:50]}")
    
    return None

def find_all_input_images():
    """
    Find all input images in the base-image folder
    
    Returns:
        list: List of tuples (image_path, is_crying_image, image_basename)
    """
    base_image_dir = Path(BASE_IMAGE_DIR)
    
    if not base_image_dir.exists():
        raise FileNotFoundError("base-image directory not found")
    
    # Common image extensions
    image_extensions = ['.png', '.jpg', '.jpeg', '.webp', '.bmp']
    
    images = []
    for file in base_image_dir.iterdir():
        if file.is_file() and file.suffix.lower() in image_extensions:
            # Check if filename contains "crying" (case insensitive)
            is_crying = "crying" in file.name.lower()
            image_basename = file.stem  # filename without extension
            images.append((str(file), is_crying, image_basename))
    
    if not images:
        raise FileNotFoundError("No image files found in base-image directory")
    
    return images

def send_to_kling(prompt, image_url, duration="5", progress_bar=None):
    """Send request to Kling API to generate video."""
    try:
        if progress_bar:
            progress_bar.set_description("Generating JWT token")
        
        # Generate JWT token
        authorization = encode_jwt_token(KLING_ACCESS_KEY, KLING_SECRET_KEY)
        
        # Handle both string and bytes return types
        if isinstance(authorization, bytes):
            authorization = authorization.decode('utf-8')
        
        if progress_bar:
            progress_bar.set_description("Sending API request")
        
        # Kling API endpoint for image to video
        endpoint = "https://api-singapore.klingai.com/v1/videos/image2video"
        
        headers = {
            "Authorization": f"Bearer {authorization}",
            "Content-Type": "application/json"
        }
        
        # Payload format from Kling documentation
        payload = {
            "model_name": "kling-v2-1",
            "mode": "std",
            "duration": duration,
            "image": image_url,
            "prompt": prompt,
            "cfg_scale": 0.5
        }
        
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("code") == 0:
                # Extract task ID
                task_data = data.get("data", {})
                task_id = task_data.get("task_id")
                
                if task_id:
                    video_url = wait_for_video_completion(task_id, authorization, progress_bar)
                    return video_url
                    
        return None
            
    except Exception as e:
        if progress_bar:
            progress_bar.set_description(f"API Error: {str(e)[:30]}")
        return None

def wait_for_video_completion(task_id, api_token, progress_bar=None, max_attempts=60, delay=5):
    """Poll Kling API for video generation completion."""
    # Query endpoint for image2video tasks
    task_query_url = f"https://api-singapore.klingai.com/v1/videos/image2video/{task_id}"
    
    # Create sub-progress bar for video generation
    with tqdm(total=max_attempts, desc="Generating video", leave=False, 
              bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}]') as video_progress:
        
        for attempt in range(max_attempts):
            try:
                headers = {
                    "Authorization": f"Bearer {api_token}",
                    "Content-Type": "application/json"
                }
                
                response = requests.get(task_query_url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get("code") == 0:
                        task_data = data.get("data", {})
                        task_status = task_data.get("task_status")
                        
                        video_progress.set_description(f"Status: {task_status}")
                        
                        if task_status == "succeed":
                            task_result = task_data.get("task_result", {})
                            videos = task_result.get("videos", [])
                            if videos:
                                video_url = videos[0].get("url")
                                video_progress.set_description("Video generated!")
                                video_progress.update(max_attempts - attempt)
                                return video_url
                        elif task_status == "failed":
                            video_progress.set_description("Generation failed")
                            return None
                            
                video_progress.update(1)
                time.sleep(delay)
                
            except Exception as e:
                video_progress.set_description(f"Error: {str(e)[:20]}")
                time.sleep(delay)
                video_progress.update(1)
    
    return None

def download_kling_video(url, save_path, progress_bar=None):
    """Download video from Kling URL."""
    try:
        if progress_bar:
            progress_bar.set_description("Downloading video")
        
        r = requests.get(url, stream=True)
        if r.status_code == 200:
            total_size = int(r.headers.get('content-length', 0))
            
            with tqdm(total=total_size, unit='B', unit_scale=True, desc="Download", 
                     leave=False, bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}') as download_progress:
                with open(save_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        download_progress.update(len(chunk))
            
            if progress_bar:
                progress_bar.update(1)
            return save_path
        else:
            raise Exception(f"Failed to download: {r.status_code}")
    except Exception as e:
        if progress_bar:
            progress_bar.set_description(f"Download failed: {str(e)[:30]}")
        return None

def process_single_image(image_path, is_crying_image, image_basename, progress_bar):
    """
    Process a single image to generate videos
    
    Returns:
        tuple: (successful_count, failed_count, successful_video_paths)
    """
    # Determine which prompts to use
    if is_crying_image:
        prompts_to_use = {"crying": PROMPTS["crying"]}
    else:
        # Use all prompts except crying
        prompts_to_use = {k: v for k, v in PROMPTS.items() if k != "crying"}
    
    # Upload image
    progress_bar.set_description(f"Uploading {image_basename}")
    image_url = upload_image_to_temporary_hosting(image_path, progress_bar)
    if not image_url:
        raise Exception(f"Failed to upload image: {image_basename}")
    progress_bar.update(1)
    
    successful = 0
    failed = 0
    successful_video_paths = []
    
    # Generate videos for selected emotions
    for emotion, prompt in prompts_to_use.items():
        progress_bar.set_description(f"Processing {image_basename}: {emotion}")
        
        try:
            # Generate video
            video_url = send_to_kling(prompt, image_url, progress_bar=progress_bar)
            progress_bar.update(1)
            
            if video_url:
                # Create output filename using original image name + emotion
                output_path = os.path.join(OUTPUT_VIDEOS_DIR, f"{image_basename}-{emotion}.mp4")
                if download_kling_video(video_url, output_path, progress_bar):
                    successful += 1
                    successful_video_paths.append(output_path)
                else:
                    failed += 1
            else:
                failed += 1
                progress_bar.update(1)  # Skip download step
                
        except Exception as e:
            failed += 1
            progress_bar.update(2)  # Skip both generate and download steps
    
    return successful, failed, successful_video_paths

def generate_all_videos():
    """
    Main function to generate all videos with progress tracking for multiple images
    """
    try:
        # Step 1: Find all input images
        print("🔍 Scanning for images...")
        all_images = find_all_input_images()
        
        # Categorize images and provide summary
        crying_images = [img for img in all_images if img[1]]
        normal_images = [img for img in all_images if not img[1]]
        
        print(f"📸 Found {len(all_images)} images:")
        if normal_images:
            print(f"   • {len(normal_images)} standard images (will generate 4 emotions each)")
        if crying_images:
            print(f"   • {len(crying_images)} crying images (will generate 1 emotion each)")
        
        # Calculate total steps
        # For each image: 1 upload + (number of videos * 2 steps per video)
        total_video_steps = 0
        for _, is_crying, _ in all_images:
            videos_per_image = 1 if is_crying else 4
            total_video_steps += 1 + (videos_per_image * 2)  # upload + (generate + download) per video
        
        with tqdm(total=total_video_steps, desc="Overall Progress", 
                  bar_format='{desc}: {percentage:3.0f}%|{bar}| {n}/{total} [{elapsed}<{remaining}]') as overall_progress:
            
            total_successful = 0
            total_failed = 0
            all_successful_video_paths = []
            
            # Process each image
            for image_path, is_crying_image, image_basename in all_images:
                try:
                    successful, failed, video_paths = process_single_image(
                        image_path, is_crying_image, image_basename, overall_progress
                    )
                    
                    total_successful += successful
                    total_failed += failed
                    all_successful_video_paths.extend(video_paths)
                    
                except Exception as e:
                    # Skip remaining steps for this image
                    videos_per_image = 1 if is_crying_image else 4
                    steps_to_skip = 1 + (videos_per_image * 2)
                    overall_progress.update(steps_to_skip)
                    total_failed += videos_per_image
                    print(f"\n❌ Failed to process {image_basename}: {e}")
            
            overall_progress.set_description("Processing completed!")
            
            # Crop all successful videos to 9:16
            if all_successful_video_paths and check_ffmpeg():
                cropped_count, crop_failed_count = crop_all_generated_videos(all_successful_video_paths, overall_progress)
                
                # Final summary with cropping results
                print(f"\n📊 Generation Summary: {total_successful} successful, {total_failed} failed")
                print(f"✂️ Cropping Summary: {cropped_count} cropped to 9:16, {crop_failed_count} crop failed")
                print("🎉 Video generation and processing completed!")
            else:
                # Final summary without cropping
                print(f"\n📊 Summary: {total_successful} successful, {total_failed} failed")
                if all_successful_video_paths and not check_ffmpeg():
                    print("⚠️ FFmpeg not available - videos remain in 16:9 format")
                print("🎉 Video generation process completed!")
            
    except Exception as e:
        print(f"\n❌ Error in video generation process: {e}")

def main():
    """Main function to run the video generator"""
    start_time = time.time()
    
    print("🎬 Hook Generator - Kling Video Creation")
    print("=" * 50)
    
    generate_all_videos()
    
    end_time = time.time()
    duration_minutes = (end_time - start_time) / 60
    print(f"\n⏱️ All tasks completed in {duration_minutes:.2f} minutes.")

# === Run with Timer ===
if __name__ == "__main__":
    # Check for API keys
    if KLING_ACCESS_KEY == "your-access-key-here":
        print("❌ Please set your KLING_ACCESS_KEY environment variable")
        exit(1)
    if KLING_SECRET_KEY == "your-secret-key-here":
        print("❌ Please set your KLING_SECRET_KEY environment variable")
        exit(1)
    
    print("🔐 API Keys loaded")
    
    # Check FFmpeg availability
    if check_ffmpeg():
        print("✅ FFmpeg detected - videos will be cropped to 9:16")
    else:
        print("⚠️ FFmpeg not found - videos will remain in 16:9 format")
        print("   Install FFmpeg to enable automatic cropping")
    
    print()
    
    main()