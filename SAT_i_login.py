import secrets
import hashlib
import json
import os
import oqs
import base64
import sys
import socket
import cv2
import struct
import socket
import gpsd
import random
import numpy
import serial
import binascii
import bchlib
import numpy as np
from datetime import datetime
import time
from cryptography.fernet import Fernet
from pypuf.simulation import XORArbiterPUF
from pypuf.io import random_inputs
import sys
import numpy
from pymavlink import mavutil
import netifaces
from memory_profiler import memory_usage
from time import process_time
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import socket
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import cv2
import threading
from queue import Queue


JSON_PATH = "login_data.json"

def check_assertion(T_i):
# Define threshold value T_delta
    T_delta = 30

    # Get the current server time (T_j_star)
    T_j_star = time.time()

    # Calculate the time difference
    time_diff = T_j_star - T_i

    # Check the assertion: T_delta <= T_i_star - T_i
    if T_delta >= time_diff:
        return True, time_diff
    else:
        return False, time_diff
		

def read_SAT_i_Reg_data_file():
    #"""Reads the JSON file and returns the data as a dictionary."""
    with open("SAT_i_Rej_data.json", 'r') as file:
        data = json.load(file)
    return data

def split_varpi_RID(concatenated_data):
    decoded_data = concatenated_data.decode()
    varpi_i, RID_i = decoded_data.split(':')

    return varpi_i, RID_i
	
def concatenate_omega_i_values(stored_PID_i, pi_1, T_i):
    return f"{stored_PID_i}:{pi_1}:{T_i}".encode()	

def hash_data(data):
    # Compute the SHA-256 hash of the given data
    hash_object = hashlib.sha256(data.encode())
    return hash_object.hexdigest()

def read_login_data_file():
    #"""Reads the JSON file and returns the data as a dictionary."""
    with open("login_data.json", 'r') as file:
        data = json.load(file)
    return data
	
def split_Omega_j_data(concatenated_data):
    decoded_data = concatenated_data.decode()
    pi_2, pi_3, T_j = decoded_data.split(':')  
    return pi_2, pi_3, T_j 

# %%%%%%%%%%%%%%%%%%%% Start of Waiting Functions %%%%%%%%%%%%%%%%%%%%%%
def safe_read_json(path):
    """Read JSON, tolerating 'mid-write' states."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError, PermissionError):
        return None

def wait_for_fields(path, required=("PPj_1", "PPj_2", "T_j"), timeout=60.0):

    deadline = time.time() + timeout
    interval = 0.05
    while time.time() < deadline:
        data = safe_read_json(path)
        if isinstance(data, dict) and all(k in data for k in required):
            return data
        time.sleep(interval)
        # gentle backoff to reduce disk churn
        interval = min(0.5, interval * 1.5)
    raise TimeoutError(f"Timed out waiting for {required} in {path}")

# %%%%%%%%%%%%%%%%%%%% End of Waiting Functions %%%%%%%%%%%%%%%%%%%%%%

def communicate_with_server():
	
    mem_before_1 = memory_usage()[0]	
# Gets Response Message from PUF
    noisy_puf_output = b'\xe3\x86\x96\x15\xe9\xbc\xc4\x80'
    # puf_output = read_uart("/dev/ttyUSB1", 9600, 0.1)
    # noisy_puf_output = bytearray(binascii.unhexlify(puf_output))
	
# %%%%%%%%%%%%%%%%%%%%%% Start of Reading registration parameters %%%%%%%%%%%%%%%%%%%%%%%

# Read the JSON file for extracting login parameters
    registration_data = read_SAT_i_Reg_data_file()
    
# Extract the values from storage
    stored_ecc = bytearray(binascii.unhexlify(registration_data.get("ecc")))
    stored_key_hash = binascii.unhexlify(registration_data.get("key_hash"))
    stored_vartheta_i = registration_data.get("vartheta_i")
    stored_PID_i = registration_data.get("PID_i")
    stored_GSS_pk = registration_data.get("GSS_pk")	
    retrieved_GSS_public_key = bytes.fromhex(stored_GSS_pk)	
	
    # print(f"stored_vartheta_i", stored_vartheta_i)	
    # print(f"stored_PID_i", stored_PID_i)	
# %%%%%%%%%%%%%%%%%%%%%% End of Reading registration parameters %%%%%%%%%%%%%%%%%%%%%%%  
    
# %%%%%%%%% Start of BCH-ECC %%%%%%%%%%%%%	
    start_CPU_time_1 = process_time()	
# BCH parameters
    BCH_T = 6
    BCH_PRIM_POLY = 487

# Initialize BCH encoder/decoder
    bch = bchlib.BCH(BCH_T, prim_poly=BCH_PRIM_POLY)

# Decode the new noisy PUF output with BCH using the stored ECC
    noisy_puf_output_bytearray = bytearray(noisy_puf_output)
    packet = noisy_puf_output_bytearray + stored_ecc
    data, ecc = packet[:-bch.ecc_bytes], packet[-bch.ecc_bytes:]

# Decode
    nerr = bch.decode(data, ecc)

# Correct
    bch.correct(data, ecc)

# Verify the corrected PUF output
    noisy_free_puf_output = bytes(data)  # Convert bytearray to bytes for printing	
    # print(f"noisy_free_puf_output", noisy_free_puf_output)
		
# %%%%%%%%% End of BCH-ECC %%%%%%%%%%%%%	

    retreived_concatenated_Data = stored_vartheta_i ^ int.from_bytes(noisy_free_puf_output,byteorder = 'big')
    end_CPU_time_1 = process_time()
	
    varpi_i, RID_i = split_varpi_RID(retreived_concatenated_Data.to_bytes((retreived_concatenated_Data.bit_length() + 7) // 8, 'big'))

    #varpi_i = varpi_i_int.hex()

    # print(f"varpi_i", varpi_i)	
    # print(f"RID_i", RID_i)

# %%%%%%%%% Start of Login Phase %%%%%%%%%%%%%	

    pi_1 = secrets.randbelow(2**128)
    # Get current time (T_i - Drone time)
    T_i = time.time()	

    start_CPU_time_2 = process_time()
    SAT_i_kem = oqs.KeyEncapsulation("Kyber512")
    CT_i, Chi_i = SAT_i_kem.encap_secret(retrieved_GSS_public_key) 
    end_CPU_time_2 = process_time()
	
    Chi_i_int = int.from_bytes(Chi_i, byteorder='big')	
	
    omega_i = concatenate_omega_i_values(stored_PID_i, pi_1, T_i)	
    omega_i_int = int.from_bytes(omega_i, byteorder='big')
	
    start_CPU_time_3 = process_time()	
    PPi_1 = Chi_i_int ^ omega_i_int

    PPi_2 = hash_data(RID_i + stored_PID_i + str(pi_1) + varpi_i + str(T_i)) 
    end_CPU_time_3 = process_time()	
	
    # print(f"CT_i", CT_i)
    # print(f"PPi_1", PPi_1)
    # print(f"PPi_2", PPi_2)
	

# Store the data in a JSON file 
    data_to_store = {
        "CT_i": binascii.hexlify(CT_i).decode('utf-8'),
        "PPi_1": PPi_1,
        "PPi_2": PPi_2,
        "T_i": T_i
    }
    with open(JSON_PATH, "w") as f:
        json.dump(data_to_store, f)
        # print("Login Data Successfully Stored within Json file")
		
    print("================================================================================================")
    print("-------------- Preparing Login Message -------------- ")
    print("================================================================================================")
    print("///// Sent Login Message <MSG1> to GSS_j ////")
    print("-------------- Sent Login Message <MSG1> Paremeters --------------")	
    print(f"CT_i (only showing 1/8 of string): {str(binascii.hexlify(CT_i).decode('utf-8'))[:16]}")
    print(f"PPi_1 (only showing 1/8 of string): {str(PPi_1)[:16]}")	
    print(f"PPi_2: {PPi_2}")	
    print(f"T_i: {T_i}")
    print("================================================================================================")


    # print("Waiting for File2 to write PPj_1, PPj_2, and T_j...")
    login_data = wait_for_fields(JSON_PATH, required=("PPj_1", "PPj_2", "T_j"), timeout=60.0)
    # print("Detected fields from File2.")

	

# Extract the values
    PPj_1 = login_data.get("PPj_1")
    PPj_2 = login_data.get("PPj_2")
    T_j   = login_data.get("T_j")

    print("================================================================================================")
    print("-------------- Waiting for Challenge Message from GSS_j -------------- ")
    print("================================================================================================")
    print("///// Received Challenge Message <MSG2> from GSS_j ////")
    print("-------------- Received Challenge Message <MSG2> Paremeters --------------")	
    print(f"PPj_1 (only showing 1/8 of string): {str(PPj_1)[:16]}")
    print(f"PPj_2: {PPj_2}")	
    print(f"T_j: {T_j}")
    print("================================================================================================")
	
    assertion_result, time_diff = check_assertion(T_j)  
        
    if assertion_result:
        print(f"----------------- Timestamp (T_j) Assertion Passed -----------------")
    else:
        print(f"----------------- Timestamp (T_j) Assertion Failed -----------------")
        sys.exit()	
		
    start_CPU_time_4 = process_time()
    Omega_j_data = PPj_1 ^ Chi_i_int
	
    retreived_pi_2, retreived_pi_3, retreived_T_j = split_Omega_j_data(Omega_j_data.to_bytes((Omega_j_data.bit_length() + 7) // 8, 'big'))
	
    PPj_2_star = hash_data(RID_i + str(retreived_pi_2) + str(int.from_bytes(noisy_free_puf_output,byteorder = 'big')) + str(retreived_T_j))


	
    assert PPj_2_star == PPj_2, f"Verification failed: PPj_2_star != PPj_2\n{sys.exit(1)}"
    # print("GSS Authentication is Successful")	
    print("================================================================================================")	    
    print("----------------- GSS_j Authentication went Sucessful -----------------")
    # print("================================================================================================")	
    session_key = hash_data(RID_i + str(pi_1) + str(retreived_pi_3) + varpi_i )	
	
	
    mem_after_1 = memory_usage()[0]	
    print("================================================================================================")
    print(f"Established Session Key with GSS_j: {session_key}")
    print("================================================================================================")
	
    end_CPU_time_4 = process_time()
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

    total_memory_consumed = mem_after_1 - mem_before_1 	
	
    cpu_time_1 = end_CPU_time_1 - start_CPU_time_1 
    cpu_time_2 = end_CPU_time_2 - start_CPU_time_2
    cpu_time_3 = end_CPU_time_3 - start_CPU_time_3
    cpu_time_4 = end_CPU_time_4 - start_CPU_time_4		

    total_cpu_time = cpu_time_1 + cpu_time_2 + cpu_time_3 + cpu_time_4		
			 	
    print("┌───────────────────── Performance Metrics ───────────────────┐")
    print(f"│ Total Memory Consumed │ {total_memory_consumed:>10.6f} MB                       │")
    print(f"│ Total CPU Time        │ {total_cpu_time:>10.6f} s                        │")
    print("└─────────────────────────────────────────────────────────────┘")			
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%		
######################################Login Message

# (Optional) clear the JSON after reading
    erase_when_done = True
    if erase_when_done:
        with open(JSON_PATH, "w") as f:
            json.dump({}, f)
        print("Cleared login_data.json")

if __name__ == "__main__":
    communicate_with_server()
