import os
import sys
import tempfile
import threading
import time
from gtts import gTTS
import PySimpleGUI as sg
import pygame
import shutil
from io import BytesIO

# Initialize pygame mixer for in-app playback
pygame.mixer.init()

# Set theme and styles using backward-compatible methods
sg.ChangeLookAndFeel('DarkTeal2')
sg.SetOptions(font=('Arial', 11))


def set_ffmpeg_path():
    """Set FFmpeg path for PyInstaller and development"""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    ffmpeg_path = os.path.join(base_path, "bin", "ffmpeg.exe")

    if os.path.exists(ffmpeg_path):
        # Add to PATH for subprocess calls
        os.environ['PATH'] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ['PATH']
    return ffmpeg_path


def generate_speech(text, lang='de', tld='de'):
    """Generate speech audio from text"""
    tts = gTTS(text=text, lang=lang, tld=tld)
    mp3_buffer = BytesIO()
    tts.write_to_fp(mp3_buffer)
    mp3_buffer.seek(0)
    return mp3_buffer


def save_audio(audio_buffer, filename):
    """Save audio buffer to file"""
    with open(filename, 'wb') as f:
        f.write(audio_buffer.getvalue())
    return filename


def play_audio(audio_buffer):
    """Play audio from buffer using pygame"""
    try:
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp.write(audio_buffer.getvalue())
            tmp_path = tmp.name

        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()
        return tmp_path
    except Exception as e:
        print(f"Playback error: {e}")
        return None


def create_window():
    """Create the main application window"""
    # Layout for the main window
    layout = [
        [sg.Text('German Voice Generator', font=('Arial', 16, 'bold'))],
        [sg.Text('Enter German phrases (one per line):')],
        [
            sg.Multiline(
                key='-INPUT-',
                size=(60, 10),
                tooltip='Paste German text here\nOne phrase per line',
                expand_x=True,
                expand_y=True
            )
        ],
        [
            sg.Button('Generate All', size=12, key='-GENERATE_ALL-'),
            sg.Button('Play All', size=12, key='-PLAY_ALL-'),
            sg.Button('Save All', size=12, key='-SAVE_ALL-'),
            sg.Button('Clear', size=12, key='-CLEAR-'),
            sg.Button('Exit', size=12, key='-EXIT-')
        ],
        [sg.HorizontalSeparator()],
        [sg.Text('Generated Phrases:', font=('Arial', 12, 'bold'))],
        [
            sg.Table(
                values=[],
                headings=['ID', 'Phrase', 'Status'],
                key='-TABLE-',
                col_widths=[5, 40, 15],
                auto_size_columns=False,
                justification='left',
                expand_x=True,
                expand_y=True,
                enable_events=True,
                select_mode=sg.TABLE_SELECT_MODE_BROWSE
            )
        ],
        [
            sg.Button('Play Selected', key='-PLAY_SELECTED-'),
            sg.Button('Save Selected', key='-SAVE_SELECTED-'),
            sg.Button('Regenerate Selected', key='-REGEN_SELECTED-')
        ],
        [sg.StatusBar('Ready', key='-STATUS-', size=(80, 1), expand_x=True)]
    ]

    return sg.Window(
        'German Voice Generator',
        layout,
        resizable=True,
        finalize=True,
        size=(800, 700)
    )


def main():
    ffmpeg_path = set_ffmpeg_path()
    window = create_window()
    generated_phrases = []
    current_playing = None

    # Main event loop
    while True:
        event, values = window.read(timeout=100)

        # Handle window close
        if event in (sg.WIN_CLOSED, '-EXIT-'):
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
            break

        # Clear input field
        if event == '-CLEAR-':
            window['-INPUT-'].update('')
            generated_phrases = []
            window['-TABLE-'].update(values=[])
            window['-STATUS-'].update('Cleared input and results')

        # Generate audio for all phrases
        if event == '-GENERATE_ALL-':
            input_text = values['-INPUT-'].strip()
            if not input_text:
                sg.PopupError('Please enter some German text!')
                continue

            phrases = [p.strip() for p in input_text.split('\n') if p.strip()]
            if not phrases:
                sg.PopupError('No valid phrases found!')
                continue

            generated_phrases = []
            window['-STATUS-'].update(f'Generating {len(phrases)} phrases...')
            window.refresh()  # Force UI update

            for i, phrase in enumerate(phrases):
                try:
                    window['-STATUS-'].update(f'Generating: "{phrase[:20]}..."')
                    window.refresh()  # Force UI update
                    audio_buffer = generate_speech(phrase)
                    generated_phrases.append({
                        'id': i + 1,
                        'text': phrase,
                        'audio': audio_buffer,
                        'status': 'Generated'
                    })
                except Exception as e:
                    generated_phrases.append({
                        'id': i + 1,
                        'text': phrase,
                        'audio': None,
                        'status': f'Error: {str(e)}'
                    })

            # Update table
            table_data = [
                [p['id'], p['text'][:80] + ('...' if len(p['text']) > 80 else ''), p['status']]
                for p in generated_phrases
            ]
            window['-TABLE-'].update(values=table_data)
            window['-STATUS-'].update(f'Successfully generated {len(phrases)} phrases!')

        # Play all generated phrases
        if event == '-PLAY_ALL-':
            if not generated_phrases:
                sg.PopupError('No phrases generated yet!')
                continue

            window['-STATUS-'].update('Playing all phrases...')
            window.refresh()  # Force UI update

            for p in generated_phrases:
                if p['audio']:
                    window['-STATUS-'].update(f'Playing: "{p["text"][:20]}..."')
                    window.refresh()  # Force UI update
                    play_audio(p['audio'])
                    # Wait for playback to finish
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                        window.refresh()  # Keep UI responsive

            window['-STATUS-'].update('Finished playing all phrases')

        # Save all generated phrases
        if event == '-SAVE_ALL-':
            if not generated_phrases:
                sg.PopupError('No phrases generated yet!')
                continue

            folder = sg.PopupGetFolder('Select folder to save MP3 files')
            if not folder:
                continue

            success_count = 0
            for p in generated_phrases:
                if p['audio']:
                    try:
                        filename = os.path.join(folder, f'german_phrase_{p["id"]}.mp3')
                        save_audio(p['audio'], filename)
                        success_count += 1
                    except Exception as e:
                        print(f"Error saving {p['id']}: {e}")

            window['-STATUS-'].update(f'Saved {success_count}/{len(generated_phrases)} files to {folder}')
            sg.Popup(f'Saved {success_count} MP3 files!', title='Success')

        # Play selected phrase
        if event == '-PLAY_SELECTED-':
            if not generated_phrases:
                sg.PopupError('No phrases generated yet!')
                continue

            selected_rows = values['-TABLE-']
            if not selected_rows:
                sg.PopupError('Please select a phrase!')
                continue

            idx = selected_rows[0]
            phrase = generated_phrases[idx]

            if not phrase['audio']:
                sg.PopupError('No audio for this phrase!')
                continue

            window['-STATUS-'].update(f'Playing: "{phrase["text"][:20]}..."')
            play_audio(phrase['audio'])

        # Save selected phrase
        if event == '-SAVE_SELECTED-':
            if not generated_phrases:
                sg.PopupError('No phrases generated yet!')
                continue

            selected_rows = values['-TABLE-']
            if not selected_rows:
                sg.PopupError('Please select a phrase!')
                continue

            idx = selected_rows[0]
            phrase = generated_phrases[idx]

            if not phrase['audio']:
                sg.PopupError('No audio for this phrase!')
                continue

            filename = sg.PopupGetFile(
                'Save MP3 file',
                save_as=True,
                default_extension='.mp3',
                file_types=(('MP3 Files', '*.mp3'),)
            if not filename:
                continue

            try:
                save_audio(phrase['audio'], filename)
                window['-STATUS-'].update(f'Saved: {os.path.basename(filename)}')
                sg.Popup(f'Saved successfully!\n{filename}', title='Success')
            except Exception as e:
                sg.PopupError(f'Error saving file: {str(e)}')

        # Regenerate selected phrase
        if event == '-REGEN_SELECTED-':
            if not generated_phrases:
                sg.PopupError('No phrases generated yet!')
                continue

            selected_rows = values['-TABLE-']
            if not selected_rows:
                sg.PopupError('Please select a phrase!')
                continue

            idx = selected_rows[0]
            phrase = generated_phrases[idx]

            try:
                window['-STATUS-'].update(f'Regenerating: "{phrase["text"][:20]}..."')
                window.refresh()  # Force UI update
                audio_buffer = generate_speech(phrase['text'])
                generated_phrases[idx]['audio'] = audio_buffer
                generated_phrases[idx]['status'] = 'Regenerated'

                # Update table
                table_data = [
                    [p['id'], p['text'][:80] + ('...' if len(p['text']) > 80 else ''), p['status']]
                    for p in generated_phrases
                ]
                window['-TABLE-'].update(values=table_data)
                window['-STATUS-'].update('Regeneration successful!')
            except Exception as e:
                generated_phrases[idx]['status'] = f'Error: {str(e)}'
                table_data = [
                    [p['id'], p['text'][:80] + ('...' if len(p['text']) > 80 else ''), p['status']]
                    for p in generated_phrases
                ]
                window['-TABLE-'].update(values=table_data)
                sg.PopupError(f'Error regenerating: {str(e)}')

        # Check if audio finished playing
        if not pygame.mixer.music.get_busy() and current_playing:
            window['-STATUS-'].update('Ready')
            current_playing = None

    window.close()


if __name__ == '__main__':
    main()