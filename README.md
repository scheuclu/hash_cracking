# Hash cracking

This is the code for my [investigation](https://www.scheuclu.com/posts/password_hash_crack) on password hash cracking.


## Requirements
- Working installation of [hashcat](https://hashcat.net/hashcat)
  - You can automatically install hashcat running `bash setup.sh`
- Working Installation of CUDA
- Python 3.8+ environment


## Usage

The hashes that I am looking for are stored in [hash_inputs.hash](./hash_inputs.hash).

I then automatically run hashcat using successively more compute intensive configurations of hashcat.

After each run, a status mail is sent to my gmail account, so I am kept up-to-date with what hashes have been found.