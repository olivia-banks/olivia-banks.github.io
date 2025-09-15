---
title: Working with Berkeley Sprite’s Homegrown CVS Wrapper (SCVS, 1992)
date: 2024-07-12
type: page
description: Checking out modules from an SCVS repository without the usage of the outdated SCVS tool.
---
I'm currently playing around with the old Sprite operating system. Sprite was a UNIX-like experimental distributed operating system developed between 1984 and 1992 at the University of California Berkeley. Sprite was developed with the intent to create a more "network aware," while keeping it invisible to the user. The primary innovation was a new network file system that utilized local client-side caching to enhance performance. Once a file is opened and some initial reads are completed, the network is accessed only on-demand, with most user actions interacting with the cache. Similar mechanisms allow remote devices to be integrated into the local computer's environment, enabling network printing and other similar functions.

Regardless, the team managed their code with a home grown tool called SCVS, which stands for "Sprite Concurrent Version System." It's described as a wrapper around CVS, which is in turn a wrapper around RCS (what is this, Javascript?). The tool is primarily implemented in one Perl file, which calls out to some other files scattered out around the Sprite source tree. I've compiled them together [here](https://git.sr.ht/~oliviabanks/scvs), and fixed some errors preventing it from running on modern Perl (the code was last updated in 1992). However, it's still a pain to use, and for some reason it errors out when checking out specific modules (the `signal` one in the kernel to be more precise).

That's why, when I wanted the code (or at least the code according to the VCS, not some random dump), I had to figure out a way to get around SCVS to read it. Turns out it's really pretty simple if you don't want to anything crazy and just want to checkout the code; in fact, I stumbled into it accidentally.

## Reading SCVS Data with CVS
The formats are pretty much the same (remember, SCVS is a wrapper). To convert it into a format CVS can read, we'll create a directory outside of the repository path:

```bash
cd ..
mkdir checkout-dump
```

Then we can go ahead and set `CVSROOT`. It should be set to the parent directory of the `CVSROOT` directory (literally named) that SCVS uses. After that, the module file found in the kernel tree should be copied into the `CVSROOT` directory.

```bash
export CVSROOT=$(realpath ../kernel)
cp ../kernel/Modules ../kernel/CVSROOT/modules
```

Then, we need to make some changes to the modules file. Since the layout here is so basic we don't have to do anything more than give each module a path:

```bash
awk '{print $1, "CVSROOT/kernel." $1}' ../kernel/CVSROOT/modules > new_modules
mv new_modules ../kernel/CVSROOT/modules
```

After that, assuming you're in the directory `checkout-dump`, you can checkout whatever you want! To check everything out, like I wanted to do for the Sprite kernel, run:

```bash
for module in $(cat ../kernel/CVSROOT/modules | awk '{print $1}'); do
	cvs checkout $module
done
```

This will run through every module and check it out. No need to worry about SCVS specific files like `SCVS.config`, indexes, or `CVSROOT.adm` administrative files.
