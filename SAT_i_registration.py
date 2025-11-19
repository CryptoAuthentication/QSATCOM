import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import secrets
import json
import binascii
import hashlib
import bchlib
import mysql.connector
import base64

mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="satcom"
)

def read_uart(port, baudrate, timeout):
    try:
        ser = serial.Serial(port, baudrate, timeout=timeout)
        
        # Send 0xEB in hex format through RX
        ser.write(b'\xEB')  # Sending 0xEB to the UART RX
        #print("Waiting for UART data...")
        while True:
            data = ser.readline()
            if data:
                #print("Received:", data)
                hex_data = ''.join([hex(byte)[2:].zfill(2) for byte in data])
                #print("Received (hex):", hex_data)
                received_string = len(hex_data)

												
				#For A7-35T with 10 MHz CLK and 9600 baud
				#Assuming 1-hexa character = 4 bits, 26-hexa characters = 104 bits
                if len(hex_data) == 26:
                # Extract the first 18 characters and ignore the first two characters "00"
                    first_18_chars = hex_data[:18]
                    final_64_hex_string = first_18_chars[2:]
                    #print(f"18 characters Hex String: {first_18_chars}")
                    #print(f"64-bit Hex String: {final_hex_string}")
                    #print("Bytes from hex", bytes.fromhex(final_64_hex_string))
                    #print("Terminating....")
                    return final_64_hex_string
                    ser.close()  # Close the serial port when done
                    break
    except serial.SerialException as e:
        print("Error:", e)
    finally:
        if ser.is_open:
            ser.close()  # Ensure the serial port is closed
			
def compute_varpi_i(identity, Delta_k):
    concatenated_data = identity + str(Delta_k)
    mid_hash = hashlib.sha256(concatenated_data.encode()).hexdigest()
    print(f"varpi_i hash",mid_hash)	
    return int(mid_hash, 16)  # Convert hexadecimal string to integer

def generate_random_identity():
    return secrets.token_hex(16)

# Function to concatenate identity and omega_i
def concatenate_values(RID_i, varpi_i, puf_i_output):
    return f"{RID_i}:{varpi_i}:{puf_i_output.hex()}".encode()
	
def concatenate_values2(varpi_i, RID_i):	
    return f"{varpi_i}:{RID_i}".encode()
	
# Function to prepare the AES key from the secret
def prepare_key(secret):
    secret_bytes = secret.to_bytes((secret.bit_length() + 7) // 8, 'big')
    digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
    digest.update(secret_bytes)
    return digest.finalize()[:16]
	
# Function to encrypt data using AES-GCM
def encrypt_data(key, data):
    iv = os.urandom(12)  # AES-GCM standard 12-byte IV
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(data) + encryptor.finalize()
    return iv, encrypted_data, encryptor.tag

def main_data_entering():

    varkappa_j = 214140748028615609671106732878009013565

    # Generate random Identity DID_j
    # DID_j = generate_random_identity()
    RID_i = "4491a201b12c1d825848801199d5a051"
    # Generate Public Identity PID_j
    # PID_j = generate_random_identity()
    PID_i = "740bc5efbab09429dd5b676d82725deb"
   
# Compute ethi
    varpi_i = compute_varpi_i(RID_i, varkappa_j)
    print(f"varpi_i", varpi_i)
#%%%%%%%%%%%%%%

# BCH parameters
    BCH_T = 6
    BCH_PRIM_POLY = 487

# Initialize BCH encoder/decoder
    bch = bchlib.BCH(BCH_T, prim_poly=BCH_PRIM_POLY)

# Noisy PUF output during registration (64-bit hexadecimal data)
    #puf_output_hex = read_uart("COM9", 9600, 0.1)
    #puf_i_output = binascii.unhexlify(puf_output_hex)
    puf_i_output = b'\xe3\x86\x96\x15\xe9\xbc\xc4\x80'
    #print(f"Original Noisy PUF Output: {puf_output_hex}")

# Encode the noisy PUF output with BCH
    ecc = bch.encode(puf_i_output)
    print("noisy_free_puf_output",puf_i_output)
# Hash the corrected PUF output to derive a secure key
    key = hashlib.sha256(puf_i_output).digest()
    print("key_hash", key)
	
# Concatenate values
    combined_data = concatenate_values(RID_i, varpi_i, puf_i_output)

# Prepare the key
    aes_key = prepare_key(varkappa_j)
	
# Encrypt the combined data
    iv, encrypted_data, tag = encrypt_data(aes_key, combined_data)
    iv_hex = iv.hex()
    encrypted_data_hex = encrypted_data.hex()
    tag_hex = tag.hex()
    aes_key_hex = aes_key.hex()	

    # print("iv_hex", iv_hex)
    # print("encrypted_data_hex", encrypted_data_hex)
    # print("tag_hex", tag_hex)
    # print("aes_key_hex", aes_key_hex)
    # exit()
    combined_vartheta_i_data = concatenate_values2(varpi_i, RID_i)
    vartheta_i = int.from_bytes(combined_vartheta_i_data, byteorder='big')  ^ int.from_bytes(puf_i_output,byteorder = 'big') 

    # print("sigma_j", sigma_j)
    # print("tau_j", tau_j)
    # exit()
#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# Store the data in a JSON file (only ECC and hashed key)
    data_to_store = {
    "ecc": binascii.hexlify(ecc).decode('utf-8'),
    "key_hash": key.hex(),
    "vartheta_i":  vartheta_i,
    "PID_i": PID_i	
    }

    with open("SAT_i_Rej_data.json", "w") as f:
        json.dump(data_to_store, f)


	
    # Assuming you have a connection and cursor created
    # mycursor = mydb.cursor()

    # sql = "INSERT INTO `protocol2`(`d_enc_records`, `d_enc_iv`, `d_enc_tag`, `d_pid`, `d_rev_status`) VALUES (%s, %s, %s, %s, %s)"
    # value = (encrypted_data_hex, iv_hex, tag_hex, PID_j, 0)
    # mycursor.execute(sql, value)

    # mydb.commit()  # Commit the changes to the database
	
    
    
    print("Real Identity of Sat:", RID_i)
    print("Public Identity of Sat:", PID_i)
    print("iv_hex", iv_hex)
    print("encrypted_data_hex", encrypted_data_hex)
    print("tag_hex", tag_hex)
    print("aes_key_hex", aes_key_hex)
    print("vartheta_i", vartheta_i)


    # print("Data stored in stored_data.json")
    # print(f"Stored ECC: {binascii.hexlify(ecc).decode('utf-8')}")
    # print(f"Stored Key Hash: {key.hex()}")
    # print(mycursor.rowcount, "record inserted in Database.")



if __name__ == "__main__":
    main_data_entering()
	
