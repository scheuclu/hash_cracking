cd ~
wget https://hashcat.net/files/hashcat-6.2.5.7z
sudo apt install p7zip-full
mkdir hashcat
7z x hashcat-6.2.5.7z -o"."
alias hashcat="~/hashcat-6.2.5/hashcat.bin"
