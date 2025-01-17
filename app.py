#!/usr/bin/env python3

from pathlib import Path
from types import SimpleNamespace
import argparse
import logging
import json
import cv2

import fastmot
import fastmot.models
from fastmot.utils import ConfigDecoder, Profiler


def motcount(inputurl, count_global, process_number):
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    optional = parser._action_groups.pop()
    required = parser.add_argument_group('required arguments')
    group = parser.add_mutually_exclusive_group()
    
    """
    required.add_argument('-i', '--input-uri', metavar="URI", required=True, help=
                          'URI to input stream\n'
                          '1) image sequence (e.g. %%06d.jpg)\n'
                          '2) video file (e.g. file.mp4)\n'
                          '3) MIPI CSI camera (e.g. csi://0)\n'
                          '4) USB camera (e.g. /dev/video0)\n'
                          '5) RTSP stream (e.g. rtsp://<user>:<password>@<ip>:<port>/<path>)\n'
                          '6) HTTP stream (e.g. http://<user>:<password>@<ip>:<port>/<path>)\n')
    """
    optional.add_argument('-c', '--config', metavar="FILE",
                          default=Path(__file__).parent / 'cfg' / 'mot.json',
                          help='path to JSON configuration file')
    optional.add_argument('-l', '--labels', metavar="FILE",
                          help='path to label names (e.g. coco.names)')
    optional.add_argument('-o', '--output-uri', metavar="URI",
                          help='URI to output video file')
    optional.add_argument('-t', '--txt', metavar="FILE",
                          help='path to output MOT Challenge format results (e.g. MOT20-01.txt)')
    optional.add_argument('-m', '--mot', action='store_true', help='run multiple object tracker')
    optional.add_argument('-s', '--show', action='store_true', help='show visualizations')
    group.add_argument('-q', '--quiet', action='store_true', help='reduce output verbosity')
    group.add_argument('-v', '--verbose', action='store_true', help='increase output verbosity')
    parser._action_groups.append(optional)
    args = parser.parse_args()
    args.mot=True
    args.show=True
    args.config='/home/geodrones/Documents/FastMOT/cfg/nano_v4tinyCH_fastobj.json'

    args.input_uri = inputurl
    
    if args.txt is not None and not args.mot:
        raise parser.error('argument -t/--txt: not allowed without argument -m/--mot')

    # set up logging
    logging.basicConfig(format='%(asctime)s [%(levelname)8s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logger = logging.getLogger(fastmot.__name__)
    if args.quiet:
        logger.setLevel(logging.WARNING)
    elif args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # load config file
    with open(args.config) as cfg_file:
        config = json.load(cfg_file, cls=ConfigDecoder, object_hook=lambda d: SimpleNamespace(**d))

    # load labels if given
    if args.labels is not None:
        with open(args.labels) as label_file:
            label_map = label_file.read().splitlines()
            fastmot.models.set_label_map(label_map)

    stream = fastmot.VideoIO(config.resize_to, args.input_uri, args.output_uri, **vars(config.stream_cfg))
    #stream2 = fastmot.VideoIO(config.resize_to, 'csi://1', args.output_uri, **vars(config.stream_cfg))

    mot = None
    #mot2 = None
    txt = None
    if args.mot:
        draw = args.show or args.output_uri is not None
        mot = fastmot.MOT(config.resize_to, count_global, **vars(config.mot_cfg), draw=draw)
        mot.reset(stream.cap_dt)
        
        #mot2 = fastmot.MOT(config.resize_to, **vars(config.mot_cfg), draw=draw)
        #mot2.reset(stream.cap_dt)
    if args.txt is not None:
        Path(args.txt).parent.mkdir(parents=True, exist_ok=True)
        txt = open(args.txt, 'w')
    if args.show:
        cv2.namedWindow('Video', cv2.WINDOW_AUTOSIZE)

        if process_number.value == 1:
            x = 200
            y = 350
        else:
            x = 1100
            y = 350
        cv2.moveWindow('Video', x, y)

    logger.info('Starting video capture...')
    stream.start_capture()
    try:
        with Profiler('app') as prof:
            while not args.show or cv2.getWindowProperty('Video', 0) >= 0:
                frame = stream.read()
                #frame2 = stream2.read()
                if frame is None:
                    break

                if args.mot:
                    mot.step(frame, count_global)
                    #mot2.step(frame)
                    if txt is not None:
                        for track in mot.visible_tracks():
                            tl = track.tlbr[:2] / config.resize_to * stream.resolution
                            br = track.tlbr[2:] / config.resize_to * stream.resolution
                            w, h = br - tl + 1
                            txt.write(f'{mot.frame_count},{track.trk_id},{tl[0]:.6f},{tl[1]:.6f},'
                                      f'{w:.6f},{h:.6f},-1,-1,-1\n')

                if args.show:
                    #two_stream_stacked = cv2.hconcat([frame,frame2])
                
                    cv2.imshow('Video', frame)
                    #cv2.imshow('Video', two_stream_stacked)
                    user_key = cv2.waitKey(1) & 0xFF 
                    if user_key == 27: #press Esc to break
                        break
                    elif user_key == 114: #press 'r' to reset count
                        mot.tracker.reset_count_found(count_global)
                if args.output_uri is not None:
                    stream.write(frame)
    finally:
        # clean up resources
        if txt is not None:
            txt.close()
        stream.release()
        cv2.destroyAllWindows()

    # timing statistics
    if args.mot:
        avg_fps = round(mot.frame_count / prof.duration)
        logger.info('Average FPS: %d', avg_fps)
        mot.print_timing_info()

from multiprocessing import Process, Value

def main():

    count_global = Value('i', 0)

    process_one = Value('i', 1)
    process_two = Value('i', 2)    
    
    p1 = Process(target=motcount, args=('csi://0', count_global, process_one, ))
    p1.start()
    
    p2 = Process(target=motcount, args=('csi://1', count_global, process_two, ))
    p2.start()
    
    #p1.join()
    #p2.join()

if __name__ == '__main__':
    main()

"""
from pathlib import Path
from types import SimpleNamespace
import argparse
import logging
import json
import cv2

import fastmot
import fastmot.models
from fastmot.utils import ConfigDecoder, Profiler


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    optional = parser._action_groups.pop()
    required = parser.add_argument_group('required arguments')
    group = parser.add_mutually_exclusive_group()
    optional.add_argument('-i', '--input-uri', metavar="URI", help=
                          'URI to input stream\n'
                          '1) image sequence (e.g. %%06d.jpg)\n'
                          '2) video file (e.g. file.mp4)\n'
                          '3) MIPI CSI camera (e.g. csi://0)\n'
                          '4) USB camera (e.g. /dev/video0)\n'
                          '5) RTSP stream (e.g. rtsp://<user>:<password>@<ip>:<port>/<path>)\n'
                          '6) HTTP stream (e.g. http://<user>:<password>@<ip>:<port>/<path>)\n')
    optional.add_argument('-c', '--config', metavar="FILE",
                          default=Path(__file__).parent / 'cfg' / 'mot.json',
                          help='path to JSON configuration file')
    optional.add_argument('-l', '--labels', metavar="FILE",
                          help='path to label names (e.g. coco.names)')
    optional.add_argument('-o', '--output-uri', metavar="URI",
                          help='URI to output video file')
    optional.add_argument('-t', '--txt', metavar="FILE",
                          help='path to output MOT Challenge format results (e.g. MOT20-01.txt)')
    optional.add_argument('-m', '--mot', action='store_true', help='run multiple object tracker')
    optional.add_argument('-s', '--show', action='store_true', help='show visualizations')
    group.add_argument('-q', '--quiet', action='store_true', help='reduce output verbosity')
    group.add_argument('-v', '--verbose', action='store_true', help='increase output verbosity')
    parser._action_groups.append(optional)
    args = parser.parse_args()
    args.mot=True
    args.show=True
    args.input_uri='csi://0'
    args.config='/home/geodrones/Documents/FastMOT/cfg/nano_v4tinyCH_fastobj.json'
    
    if args.txt is not None and not args.mot:
        raise parser.error('argument -t/--txt: not allowed without argument -m/--mot')

    # set up logging
    logging.basicConfig(format='%(asctime)s [%(levelname)8s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logger = logging.getLogger(fastmot.__name__)
    if args.quiet:
        logger.setLevel(logging.WARNING)
    elif args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # load config file
    with open(args.config) as cfg_file:
        config = json.load(cfg_file, cls=ConfigDecoder, object_hook=lambda d: SimpleNamespace(**d))

    # load labels if given
    if args.labels is not None:
        with open(args.labels) as label_file:
            label_map = label_file.read().splitlines()
            fastmot.models.set_label_map(label_map)

    stream = fastmot.VideoIO(config.resize_to, args.input_uri, args.output_uri, **vars(config.stream_cfg))
    #stream2 = fastmot.VideoIO(config.resize_to, 'csi://1', args.output_uri, **vars(config.stream_cfg))

    mot = None
    #mot2 = None
    txt = None
    if args.mot:
        draw = args.show or args.output_uri is not None
        mot = fastmot.MOT(config.resize_to, **vars(config.mot_cfg), draw=draw)
        mot.reset(stream.cap_dt)
        
        #mot2 = fastmot.MOT(config.resize_to, **vars(config.mot_cfg), draw=draw)
        #mot2.reset(stream.cap_dt)
    if args.txt is not None:
        Path(args.txt).parent.mkdir(parents=True, exist_ok=True)
        txt = open(args.txt, 'w')
    if args.show:
        cv2.namedWindow('Video', cv2.WINDOW_AUTOSIZE)

    logger.info('Starting video capture...')
    stream.start_capture()
    try:
        with Profiler('app') as prof:
            while not args.show or cv2.getWindowProperty('Video', 0) >= 0:
                frame = stream.read()
                #frame2 = stream2.read()
                if frame is None:
                    break

                if args.mot:
                    mot.step(frame)
                    #mot2.step(frame)
                    if txt is not None:
                        for track in mot.visible_tracks():
                            tl = track.tlbr[:2] / config.resize_to * stream.resolution
                            br = track.tlbr[2:] / config.resize_to * stream.resolution
                            w, h = br - tl + 1
                            txt.write(f'{mot.frame_count},{track.trk_id},{tl[0]:.6f},{tl[1]:.6f},'
                                      f'{w:.6f},{h:.6f},-1,-1,-1\n')

                if args.show:
                    #two_stream_stacked = cv2.hconcat([frame,frame2])
                
                    cv2.imshow('Video', frame)
                    #cv2.imshow('Video', two_stream_stacked)
                    user_key = cv2.waitKey(1) & 0xFF 
                    if user_key == 27: #press Esc to break
                        break
                    elif user_key == 114: #press 'r' to reset count
                        mot.tracker.reset_count_found()
                if args.output_uri is not None:
                    stream.write(frame)
    finally:
        # clean up resources
        if txt is not None:
            txt.close()
        stream.release()
        cv2.destroyAllWindows()

    # timing statistics
    if args.mot:
        avg_fps = round(mot.frame_count / prof.duration)
        logger.info('Average FPS: %d', avg_fps)
        mot.print_timing_info()


if __name__ == '__main__':
    main()

"""
