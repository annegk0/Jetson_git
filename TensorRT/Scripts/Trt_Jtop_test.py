
import numpy as np
import time
import csv

import librosa
from torchlibrosa.stft import Spectrogram, LogmelFilterBank
import torch
from torch import nn


import pycuda.driver as cuda
import pycuda.autoinit
import tensorrt as trt

import matplotlib.pyplot as plt
plt.switch_backend('agg')
from threading import Thread
from jtop import jtop
import time
import  csv
from datetime import datetime, timedelta


thread_stop=False
start_value=datetime.now()
inference_start=datetime.now()
start_event_main=cuda.Event()
start_time_infer=datetime.now()
start_audio_tag=datetime.now()
start_warmUp=datetime.now()
end_warmpUp=datetime.now()

def power_conso():
    global start_value
    global start_warmUp
    global start_audio_tag
    print("start_value avt assignement", start_value)
    with jtop() as jetson:
    # jetson.ok() will provide the proper update frequency
        global thread_stop
        global end_warmpUp
        data={"Total Power" : [],"GPU" : [], "Time":[]}
        while jetson.ok() and thread_stop==False:
            # Read tegra stats
            data["Total Power"].append(jetson.stats['Power TOT'])
            data["GPU"].append(jetson.stats['GPU'])
            data["Time"].append(jetson.stats['time'])
    
    start_value = data["Time"][0]
    print("start_value apres", start_value)
    data["Time"] = [(time_value - start_audio_tag).total_seconds() for time_value in data["Time"] ]
    
    plt.plot(data["Time"], data["GPU"])
    plt.xlabel("Time (s)")
    plt.ylabel("Power Consumption GPU (mW)")
    print("start_time_infer",start_time_infer)
    print("start_warmUp",start_warmUp)
    print("end_warmpUp",end_warmpUp)
    plt.axvline(x=start_warmUp, color='red')
    plt.axvline(x=start_time_infer, color='green')
    plt.axvline(x=end_warmpUp, color='yellow')
    plt.savefig("/home/brain/Documents/Test/audioset_tagging_cnn/TensorRT/results/Trt_Jetson_GPU_Consumption.png")
    
    with open("/home/brain/Documents/Test/audioset_tagging_cnn/TensorRT/results/power_conso.csv", 'w', newline='') as f:
    	writer = csv.writer(f)
    	writer.writerow(data.keys())
    	writer.writerows(zip(*data.values()))
    
    
    
def audio_tagging(output_data):
        

	
	global start_event_main
	start_event_main.record()
	global start_audio_tag
	start_audio_tag = datetime.now()
	print("start_audio_tag",start_audio_tag)
	#time.sleep(10)
	input_data= np.load('/home/brain/Documents/AudioNN_Portage/MobileNetTens/image_701x64.npy') # attention ! à modifier en cas de changement de fichier 
	

	# Load trt engine file
	model_path_trt = "/home/brain/Documents/Test/audioset_tagging_cnn/TensorRT/mobileNet_engine.trt"

	with open(model_path_trt, 'rb') as f:
		engine_data = f.read()
		
	runtime = trt.Runtime(trt.Logger(trt.Logger.WARNING))
	engine = runtime.deserialize_cuda_engine(engine_data)
	context = engine.create_execution_context()

	# Size Output :	
	output_shape = (526,)  
	
	# GPU Warm Up 
	global start_warmUp 
	start_warmUp=(datetime.now() - start_audio_tag).total_seconds()
	print("start warm up : ", start_warmUp)
	dummy_input = np.random.rand(1,224000)
	dummy_output = np.empty(output_shape, dtype=np.float32)
	dummy_input_buf = cuda.mem_alloc(dummy_input.nbytes)
	cuda.memcpy_htod_async(dummy_input_buf, dummy_input)
	dummy_output_buf = cuda.mem_alloc(output_shape[0] * np.dtype(np.float32).itemsize)
	context.execute_v2(bindings=[int(dummy_input_buf),int(dummy_output_buf)])
	cuda.memcpy_dtoh_async(dummy_output, dummy_output_buf)
	global end_warmpUp
	end_warmpUp=(datetime.now() - start_audio_tag).total_seconds()

	# Allocate input and output buffers on the GPU :
	input_buf = cuda.mem_alloc(input_data.nbytes)
	output_buf = cuda.mem_alloc(output_shape[0] * np.dtype(np.float32).itemsize)
	
	# Transfer input data to GPU
	cuda.memcpy_htod_async(input_buf, input_data)
	
	# Inference Time Variables & Start Recording :
	global start_value
	global inference_start
	global start_time_infer
	start_infer=cuda.Event()
	end_event=cuda.Event()
	start_infer.record()
	start_time_infer=start_event_main.time_till(start_infer)/1000
	print(f"start_time_infer : {start_time_infer } s")
	#print("start_time_infer - start_time",(start_time_infer - start_value).total_seconds())
	inference_start= (datetime.now() - start_value).total_seconds()
	
	# Run inference
	context.execute_v2(bindings=[int(input_buf),int(output_buf)])
	
	# End Recording & Calculate Inference Duration: 
	end_event.record()
	#Calculate the run length
	end_event.synchronize()
	elapsed_time=start_infer.time_till(end_event)/1000
	print(f"Inference Time : {elapsed_time } s")
	
	# Transfer output data from GPU :
	cuda.memcpy_dtoh_async(output_data, output_buf)
	
	print("end inf",(datetime.now() - start_audio_tag).total_seconds())
	# Stop Consumption Recording :
	global thread_stop
	time.sleep(5)
	thread_stop=True
    

if __name__ == '__main__':

    output_shape = (526,)  # Example output shape
    output_data = np.empty(output_shape, dtype=np.float32)
    end_event_main=cuda.Event()
    #global start_event_main
    #start_event_main.record()
    thread_conso=Thread(target = power_conso)
    thread_conso.start()
    thread_model=Thread(target = audio_tagging, args=(output_data,))
    end_event_main.record()
   
    # Print Result 

    audio_tagging(output_data)
    classes_name = np.load("/home/brain/Documents/AudioNN_Portage/MobileNetTens/classes.npy")

    
    framewise_output = output_data
    sorted_indexes = np.argsort(framewise_output)[::-1]

    top_k = 10  # Show top results
    top_result_mat = framewise_output[sorted_indexes[0 : top_k]]    
    top_classes = classes_name[sorted_indexes[0 : top_k]]
    for i in range(top_k):
        print(i+1, "result : ", top_result_mat[i], " with class : ",top_classes[i],"\n")

