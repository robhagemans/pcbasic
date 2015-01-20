# PC-BASIC 3.23 distributions

Packaged releases are provided for the following operating systems:  
-     **Windows** (XP and later)  
-     **Mac OS X** (10.6 and later)   
-     **Linux** (on i386/x86-64 architecture)  

You can find them on this page organised in folders by release number. There is no fixed release schedule or roadmap, so new releases will appear when I feel like it. Some releases include an experimental Android package, but you shouldn't expect much in the way of support for this at the moment.  

However, since PC-BASIC is based on Python, it can run on a large range of different operating systems. This is where the **source distribution** comes in. There is no difference in performance between the source and packaged releases; indeed, the packaged releases are simply the source wrapped up with a Python interpreter and all the necessary modules. The only disadvantage of the source distribution is that you will need to install Python and all dependencies. See the `README.md` file inside the source tarball for the list of Python modules you need to install.   

The source distribution on this page is intended for users and does not contain all development files. In particular, tests and packaging scripts are left out. If you're interested in development, it's best to get your own full copy of the Git repository on the Sourceforge [Code](https://sourceforge.net/p/pcbasic/code/) page. 

# Bugs, issues, and feature requests

PC-BASIC is still in beta, meaning that it works quite well but you should expect things to break now and then. I try to avoid regressions, but sometimes a newer version may break something that worked before. Sorry about that. Consider that by downloading a beta version you're agreeing to try and help me to find and solve bugs so that the next release is going to be better.   

If (_when_) you find bugs or regressions, please let me know by posting a message on the [Discussion Forum](https://sourceforge.net/p/pcbasic/discussion/). **After you posted, please visit back in the next few days**: often, it's not obvious to me from the first report what the exact problem is, since people use different setups, have different expectations and make different assumptions. I'll usually reply fairly quickly to ask you for some more information. For that same reason, **please don't use the Reviews section to leave feedback about bugs**: there's no way for me to find out more about what the exact issue is, so in all probability it won't get solved.

Rob
