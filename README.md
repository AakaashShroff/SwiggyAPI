# SwiggyAPI
Order food from swiggy from your terminal with the dish you want to have being the single input needed.

User Needs Modification:
----------------------------------------------------
address_div_xpath and ADDRESS_TO_SELECT variable values to be changed to your saved home address name.

PHONE_NUMBER is to be changed to your swiggy account number.

Modify restaurant_dict based on your needs. The keys are the restaurant and values are the dishes it offers, the user input is a dish the user wants to have and the respective key(restaurant name) is used to run the script further.

Script additions made based on tests and thoughts:
----------------------------------------------------
The script is well enough to handle a few pop up cases I encountered while testing and orders food like a charm.

The payment method best fit is swiggy money as other payment methods need human intervention and I have written the code to use that as payment method.

The script takes care of applying any non-payment related (or only restaurant/app coupon) as they dont require human intervention. If no applicable codes appear, it proceeds with payment. (Honey extension does not support swiggy, if not I had planned on using that to apply coupons).

Usage:
----------------------------------------------------
The first time you run the script it will enter your phone number in the login form, youll have to proceed manually and enter the OTP.

Once you log in the first time successfully, you should see a login_cookies.json. This file will be used to login in future till the cookies expire.

Based on the dictionary you hard coded you can order the dishes with a single input -  The dish you want. Enjoy :).
-----------------------------------------------------
Note: This script in my personal use will be further updated to use nltk to order food similar to input(typo errors cause a rerun to order successfully as value is not found in the dictionary). This will further be converted to a flask API which I might add here once done. This api will be integrated on my local server for my personal AI assistant to order food for me with a single voice command.
