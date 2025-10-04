import csv
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import VerticalGradiantColorMask

# Text to encode
text = "westin.musser@mindsmatterseattle.org"
def generate_qr_code(text):
    # Generate QR code
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(text)

    img = qr.make_image(image_factory=StyledPilImage, color_mask=VerticalGradiantColorMask(bottom_color=(0, 0, 0), top_color=(0, 56, 150)), embeded_image_path="logo.png")
    img.save(f"volunteers/{text}.png")

emails = ['jocelyn.freed@mindsmatterseattle.org']

# with open('VRM_Volunteer_Operations_Main_v2.2 - VOLUNTEERS.csv', 'r') as file:
#     reader = csv.reader(file)
for email in emails:
    # email = row[4]
    # email = 'thomas.guyton@mindsmatterseattle.org'
    generate_qr_code(email)
    print(f"QR code generated for {email}")