import socket
import threading
import mysql.connector
import oqs
import json
import hashlib
import binascii
import re
import getpass
import sys
import os
import secrets
import time
from time import process_time
import webbrowser
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from memory_profiler import memory_usage





mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="satcom"
)
mycursor = mydb.cursor()

def check_assertion(T_i):
# Define threshold value T_delta (1 second)
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


def load_key():
    # Load GSS_k's private key from the JSON file
    with open("privatekey.json", "r") as priv_file:
        private_key = bytes.fromhex(json.load(priv_file)["private_key"])
    return private_key
	
	
################################# Start of Keyber-KEM ######################################	
# Load the private key
GSS_j_sk = load_key()
GSS_j_kem = oqs.KeyEncapsulation("Kyber512")
GSS_j_kem.secret_key = GSS_j_sk
################################# End of Keyber-KEM ######################################	
varkappa_j = 214140748028615609671106732878009013565

def split_Omega_i_data(concatenated_data):
    decoded_data = concatenated_data.decode()
    PID_i, pi_1, T_i = decoded_data.split(':')  
    return PID_i, pi_1, T_i 
	
def extract_records(PID_i):

    sql_new = "SELECT `sat_i_pid`, `sat_i_enc_records`, `sat_i_enc_iv`, `sat_i_enc_tag`, `sat_id` FROM `sat_i` WHERE `sat_i_pid` = %s AND `sat_i_rev_status` = 0"	
    mycursor.execute(sql_new, (PID_i,))
    records_new = mycursor.fetchall()

    extracted_values = None

# Extract and compare the values from the tuples
    for record in records_new:
        if PID_i == record[0]:
            extracted_values = record[1:]

    return extracted_values	
	
	
# Function to prepare the AES key from the secret
def prepare_key(secret):
    secret_bytes = secret.to_bytes((secret.bit_length() + 7) // 8, 'big')
    digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
    digest.update(secret_bytes)
    return digest.finalize()[:16]

# Function to decrypt data using AES-GCM
def decrypt_data(key, iv, encrypted_data, tag):
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend())
    decryptor = cipher.decryptor()
    return decryptor.update(encrypted_data) + decryptor.finalize()
	
def split_dec_values(data):
    decoded_data = data.decode()
    RID_i, varpi_i, puf_i_hex  = decoded_data.split(':')
    puf_i = bytes.fromhex(puf_i_hex)
    return RID_i, varpi_i, puf_i	
	
def hash_data(data):
    # Compute the SHA-256 hash of the given data
    hash_object = hashlib.sha256(data.encode())
    return hash_object.hexdigest()
	
def concatenate_omega_i_values(pi_2, pi_3, T_j):
    return f"{pi_2}:{pi_3}:{T_j}".encode()
	
def read_login_data_file():
    #"""Reads the JSON file and returns the data as a dictionary."""
    with open("login_data.json", 'r') as file:
        data = json.load(file)
    return data
	
def write_login_data_file(data):
    with open("data.json", 'w') as file:
        json.dump(data, file, indent=4)
	

# %%%%%%%%%%%%%%%%%%%% Start of Waiting Functions %%%%%%%%%%%%%%%%%%%%%%
# Safe JSON reader (handles missing or malformed files gracefully)
# Safe JSON reader
def safe_read_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # File might still be written or corrupted
        return None


# Wait until the JSON file contains the required field(s)
def wait_for_fields(path, required=("RxData",), timeout=60.0):
    deadline = time.time() + timeout
    interval = 0.05
    while time.time() < deadline:
        data = safe_read_json(path)
        if isinstance(data, dict) and all(k in data for k in required):
            return data
        time.sleep(interval)
        interval = min(0.5, interval * 1.5)  # gentle backoff
    raise TimeoutError(f"Timed out waiting for {required} in {path}")

# %%%%%%%%%%%%%%%%%%%% End of Waiting Functions %%%%%%%%%%%%%%%%%%%%%%

def GSS_j_Login():
    JSON_PATH = r"data.json"
###################################### Start of Extracting Login Message 

    print("================================================================================================")
    print("-------------- Waiting for Login Message from Satellite -------------- ")




# This will block until the file contains "RxData"
    login_data = wait_for_fields(JSON_PATH, required=("RxData",), timeout=60.0)

# Once available, extract and process
    rx_string = login_data["RxData"]
    parts = rx_string.split(":")
    if len(parts) != 4:
        raise ValueError(f"Expected 4 values in RxData but got {len(parts)}")

    CT_i, PP_1, PPi_2, T_1 = parts

    PPi_1 = int(PP_1)
    T_i = float(T_1)
    print("CT_i:", CT_i)
    print("PPi_1:", PPi_1)
    print("PPi_2:", PPi_2)
    print("T_i:", T_i)
	
# Extract the values
    # CT_i = login_data.get("CT_i")
    # PPi_1 = login_data.get("PPi_1")
    # PPi_2 = login_data.get("PPi_2")
    # T_i = login_data.get("T_i")
    retreived_CT_i_bytes = bytes.fromhex(CT_i)
    print("================================================================================================")
    print("///// Received login Message <MSG1> from Satellite ////")
    print("-------------- Received login Message <MSG1> Paremeters --------------")	
    print(f"CT_i (only showing 1/8 of string): {str(CT_i)[:16]}")
    print(f"PPi_1 (only showing 1/8 of string): {str(PPi_1)[:16]}")	
    print(f"PPi_2: {PPi_2}")	
    print(f"T_i: {T_i}")
    print("================================================================================================")	

###################################### End of Extracting Login Message 
    mem_before_1 = memory_usage()[0]
    assertion_result, time_diff = check_assertion(T_i)  
        
    if assertion_result:
        print(f"----------------- Timestamp (T_i) Assertion Passed -----------------")
    else:
        print(f"----------------- Timestamp (T_i) Assertion Failed -----------------")
        sys.exit()


    start_CPU_time_1 = process_time() 
    retreived_Chi_i = GSS_j_kem.decap_secret(retreived_CT_i_bytes) 
    # print(f"retreived_Chi_i: {retreived_Chi_i}")
	
    Chi_i_int = int.from_bytes(retreived_Chi_i, byteorder='big')

    Omega_i_data = PPi_1 ^ Chi_i_int
    end_CPU_time_1 = process_time() 
	
    retreived_PID_i, retreived_pi_1, retreived_T_i = split_Omega_i_data(Omega_i_data.to_bytes((Omega_i_data.bit_length() + 7) // 8, 'big'))	

    # print(f"retreived_PID_i, {retreived_PID_i}")
    # print(f"retreived_pi_1, {retreived_pi_1}")
    # print(f"retreived_T_i, {retreived_T_i}")
	
	
    extracted_values = extract_records(retreived_PID_i)
    if extracted_values:
        sat_enc_records = extracted_values[0]  #Extracts d_enc_records from queried data
        sat_enc_iv = extracted_values[1]  #Extracts d_enc_records from queried data
        sat_enc_tag = extracted_values[2]  #Extracts d_enc_records from queried data
        sat_id = extracted_values[3]  #Extracts d_enc_records from queried data
			
        # print(f"sat_enc_records: {sat_enc_records}")
        # print(f"sat_enc_iv: {sat_enc_iv}")
        # print(f"sat_enc_tag: {sat_enc_tag}")
        # print(f"Primay key: {sat_id}")	
		
################################# Start of AES-GCM ######################################	

# Prepare key
    start_CPU_time_2 = process_time()
    aes_key = prepare_key(varkappa_j)

# Convert hex values back to bytes
    iv_bytes = bytes.fromhex(sat_enc_iv)
    encrypted_data_bytes = bytes.fromhex(sat_enc_records)
    tag_bytes = bytes.fromhex(sat_enc_tag)
           # print("Recovered bytes data")
           # print("iv_bytes", iv_bytes)
           # print("encrypted_data_bytes", encrypted_data_bytes)
           # print("tag_bytes", tag_bytes)
    decrypted_data = decrypt_data(aes_key, iv_bytes, encrypted_data_bytes, tag_bytes)
    end_CPU_time_2 = process_time()	
    RID_i, varpi_i, puf_i = split_dec_values(decrypted_data)
    
    puf_i_int = int.from_bytes(puf_i,byteorder = 'big')
    
    print(f"Decrypted RID_i: {RID_i}")
    print(f"Decrypted puf_output: {puf_i}")
    print(f"Decrypted varpi_i: {varpi_i}")
################################# End of AES-GCM #####################################
    start_CPU_time_3 = process_time()	
	# Verifies the equality of Mi_2
    PPi_2_star = hash_data(RID_i + retreived_PID_i + str(retreived_pi_1) + varpi_i + str(retreived_T_i))
    end_CPU_time_3 = process_time()
    assert PPi_2_star == PPi_2, f"Verification failed: PPi_2_star != PPi_2\n{sys.exit(1)}"
    # print("Satellite Authentication is Successful")
    print("================================================================================================")	    
    print("----------------- Satellite Authentication went Sucessful -----------------")
    # print("================================================================================================")		
################################# Start of Challenge Message #####################################	
    pi_2 = secrets.randbelow(2**128)
    pi_3 = secrets.randbelow(2**128)
    T_j = time.time()
	
    omega_j = concatenate_omega_i_values(pi_2, pi_3, T_j)	
    omega_j_int = int.from_bytes(omega_j, byteorder='big')

    start_CPU_time_4 = process_time()
    PPj_1 = omega_j_int ^ Chi_i_int
    PPj_2 = hash_data(RID_i + str(pi_2) + str(puf_i_int) + str(T_j))
    session_key = hash_data(RID_i + str(retreived_pi_1) + str(pi_3) + varpi_i )
    end_CPU_time_4 = process_time()	
    # print(f"PPj_1: {PPj_1}")
    # print(f"PPj_2: {PPj_2}")
    # print(f"T_j: {T_j}")
    # print(f"session_key: {session_key}")
    
    mem_after_1 = memory_usage()[0]		
#%%%%%%%%%%%%%%%%%%%
# Store them in the data dictionary
    login_data["PPj_1"] = str(PPj_1)
    login_data["PPj_2"] = PPj_2
    login_data["T_j"] = str(T_j)

# Write updated data back to the JSON file
    write_login_data_file(login_data)

    # print("Values successfully written to login_data.json")
    print("================================================================================================")			
    print("///// Sent Challenge Message <MSG2> to Satellite ///// ")
    print("================================================================================================")	
    print("/////// Sent Message <MSG_2> parameters ///////")
    print(f"PPj_1 (only showing 1/8 of string): {str(PPj_1)[:16]}")	
    print(f"PPj_2: {PPj_2}")		
    print(f"T_j: {T_j}")		
    print("================================================================================================")
    print(f"Established Session Key with Satellite: {session_key}")
    print("================================================================================================")
	
	
	
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
if __name__ == "__main__":
    GSS_j_Login()
