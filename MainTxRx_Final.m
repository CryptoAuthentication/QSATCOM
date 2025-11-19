%function [a] = MainTxRx(Data,y)
clear
a = 3;

% Communicating with Raspberry pi
r = raspi('192.168.1.91','remote','abc135137');

% Read JSON text from the file
raw = system(r, 'cat /home/remote/login_params.json');

% Decode JSON into a MATLAB struct
J = jsondecode(string(raw));

% Access fields
CT_i  = J.CT_i;
PPi_1 = J.PPi_1;
PPi_2 = J.PPi_2;
T_i   = (J.T_i);   % convert to numeric if desired

% ---- Now you can use them in any MATLAB operation ----
format long
% Example: display values
fprintf('CT_i: %s\n', CT_i);
fprintf('PPi_1: %s\n', PPi_1);
fprintf('PPi_2: %s\n', PPi_2);
fprintf('Timestamp: %s\n', char(T_i));
%char(T_i)


%% First Tx and Rx
y = 1;
if y == 1
    Msg1 = [CT_i,':',PPi_1,':',PPi_2,':',char(T_i),':::'];
    len = length(double(Msg1));
    Data1 = Msg1;
    SDRTx = PlutoTx(Data1);
    release(SDRTx);
    pause(5)

    [SDRRx,TxData2] = PlutoRx();
    
    y = 2;


    cmd = "python3 - <<'PY'" + newline + ...
"import json" + newline + ...
"f = '/home/remote/login_params.json'" + newline + ...
"with open(f) as fh:" + newline + ...
"    J = json.load(fh)" + newline + ...
"J.update({'TxData2':'" + TxData2 + "'})" + newline + ...
"with open(f,'w') as fh:" + newline + ...
"    json.dump(J, fh, indent=2)" + newline + ...
"print('UPDATED')" + newline + ...
"PY" + newline;

% Convert to char for raspi/system:
out = system(r, char(cmd));   % <-- key change
disp(out);

end

