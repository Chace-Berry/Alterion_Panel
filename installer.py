

import customtkinter as ctk
# Alterion Panel Installer - CustomTkinter Native UI
import tkinter as tk
# from tkinter import Canvas  # Removed unused import
from PIL import Image, ImageTk
import io
import webbrowser
import requests
import tempfile
import shutil
import sys
import os
import threading


LOGO_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480.64 150.8"><defs><style>.cls-1,.cls-2{fill:none;stroke:#d8e7e8;stroke-miterlimit:10;}.cls-1{stroke-width:6px;}.cls-2{stroke-width:2px;}</style></defs><g id="Layer_2" data-name="Layer 2"><g id="Layer_1-2" data-name="Layer 1"><g id="Layer_1-2-2" data-name="Layer 1-2"><polyline class="cls-1" points="2.72 83.97 33.98 16.57 65.24 83.97"/><path class="cls-1" d="M37.69,84,29.15,63.59Z"/><line class="cls-1" x1="87.96" y1="13.95" x2="87.96" y2="66.04"/><polyline class="cls-1" points="87.96 73.59 87.96 82.12 122.18 82.12"/><line class="cls-1" x1="126.52" y1="15.55" x2="158.94" y2="15.55"/><line class="cls-1" x1="162.52" y1="15.55" x2="168.9" y2="15.55"/><line class="cls-1" x1="147.2" y1="15.55" x2="147.2" y2="84.99"/><polyline class="cls-1" points="213.41 17.3 183.53 17.3 183.53 58.92"/><line class="cls-2" x1="191.7" y1="63" x2="180.64" y2="63"/><polyline class="cls-1" points="183.61 62 183.61 83.24 216.02 83.24"/><path class="cls-1" d="M224,42V16.44c1.3-.24,17.54-3,28.42,8.51a29.59,29.59,0,0,1,7.66,17A20.3,20.3,0,0,1,257,55.27c-5.29,8-14.53,8.86-15.66,8.94H224"/><line class="cls-1" x1="262.46" y1="84.55" x2="244.61" y2="63.68"/><line class="cls-1" x1="281.5" y1="16.23" x2="281.5" y2="84.31"/><path class="cls-1" d="M300.73,36c0-3.74,8.86-18.65,29.28-18.55,19.81.09,30.88,13,31.83,30.47,1,18.48-11.19,35.23-32.17,35.23a43.29,43.29,0,0,1-19.07-4.61"/><polyline class="cls-1" points="393.32 86.23 393.32 20.87 403.03 37.72"/><polyline class="cls-1" points="423.45 60.61 433.15 76.69 433.15 14.31"/></g><line class="cls-1" x1="87.96" y1="13.95" x2="87.96" y2="66.04"/><polyline class="cls-1" points="87.96 73.59 87.96 82.12 122.18 82.12"/><line class="cls-2" x1="151.73" y1="122.63" x2="151.73" y2="150.8"/><polyline class="cls-2" points="168.18 149.8 187.06 102.64 205.94 149.8"/><path class="cls-2" d="M189.3,149.8l-5.16-14.67Z"/><polyline class="cls-2" points="219.31 149.8 219.31 104.3 225.09 116.03"/><polyline class="cls-2" points="241.6 133.83 247.44 145.57 247.44 100.03"/><polyline class="cls-2" points="279.65 101.02 258.01 101.02 258.01 131.06"/><line class="cls-2" x1="263.93" y1="133.99" x2="255.92" y2="133.99"/><polyline class="cls-2" points="258.07 133.27 258.07 148.79 281.54 148.79"/><line class="cls-2" x1="286.35" y1="100.03" x2="286.35" y2="137.29"/><polyline class="cls-2" points="286.35 142.69 286.35 148.79 311.45 148.79"/><path class="cls-2" d="M151.73,119.1V100.72l3.69,0h0c11.32-.3,19.26,9.33,18.05,17.71-1,7-8.45,13.25-17.61,12.9"/><line class="cls-2" x1="457.51" y1="1.41" x2="459.95" y2="1.41"/><line class="cls-2" x1="443.74" y1="1.41" x2="456.14" y2="1.41"/><line class="cls-2" x1="451.65" y1="1.41" x2="451.65" y2="18.99"/><path class="cls-2" d="M466.53,19V2.71l8,8.51"/><path class="cls-2" d="M474.87,8.3l4.77-5.59V19"/></g></g></svg>'''
DISCORD_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" x="0px" y="0px" width="100" height="100" viewBox="0 0 48 48">
<path fill="#536dfe" d="M39.248,10.177c-2.804-1.287-5.812-2.235-8.956-2.778c-0.057-0.01-0.114,0.016-0.144,0.068	c-0.387,0.688-0.815,1.585-1.115,2.291c-3.382-0.506-6.747-0.506-10.059,0c-0.3-0.721-0.744-1.603-1.133-2.291	c-0.03-0.051-0.087-0.077-0.144-0.068c-3.143,0.541-6.15,1.489-8.956,2.778c-0.024,0.01-0.045,0.028-0.059,0.051	c-5.704,8.522-7.267,16.835-6.5,25.044c0.003,0.04,0.026,0.079,0.057,0.103c3.763,2.764,7.409,4.442,10.987,5.554	c0.057,0.017,0.118-0.003,0.154-0.051c0.846-1.156,1.601-2.374,2.248-3.656c0.038-0.075,0.002-0.164-0.076-0.194	c-1.197-0.454-2.336-1.007-3.432-1.636c-0.087-0.051-0.094-0.175-0.014-0.234c0.231-0.173,0.461-0.353,0.682-0.534	c0.04-0.033,0.095-0.04,0.142-0.019c7.201,3.288,14.997,3.288,22.113,0c0.047-0.023,0.102-0.016,0.144,0.017	c0.22,0.182,0.451,0.363,0.683,0.536c0.08,0.059,0.075,0.183-0.012,0.234c-1.096,0.641-2.236,1.182-3.434,1.634	c-0.078,0.03-0.113,0.12-0.075,0.196c0.661,1.28,1.415,2.498,2.246,3.654c0.035,0.049,0.097,0.07,0.154,0.052	c3.595-1.112,7.241-2.79,11.004-5.554c0.033-0.024,0.054-0.061,0.057-0.101c0.917-9.491-1.537-17.735-6.505-25.044	C39.293,10.205,39.272,10.187,39.248,10.177z M16.703,30.273c-2.168,0-3.954-1.99-3.954-4.435s1.752-4.435,3.954-4.435	c2.22,0,3.989,2.008,3.954,4.435C20.658,28.282,18.906,30.273,16.703,30.273z M31.324,30.273c-2.168,0-3.954-1.99-3.954-4.435	s1.752-4.435,3.954-4.435c2.22,0,3.989,2.008,3.954,4.435C35.278,28.282,33.544,30.273,31.324,30.273z"></path>
</svg>'''
GITHUB_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" x="0px" y="0px" width="100" height="100" viewBox="0,0,256,256">
<g fill="#ffffff" fill-rule="nonzero" stroke="none" stroke-width="1" stroke-linecap="butt" stroke-linejoin="miter" stroke-miterlimit="10" stroke-dasharray="" stroke-dashoffset="0" font-family="none" font-weight="none" font-size="none" text-anchor="none" style="mix-blend-mode: normal"><g transform="scale(5.12,5.12)"><path d="M17.791,46.836c0.711,-0.306 1.209,-1.013 1.209,-1.836v-5.4c0,-0.197 0.016,-0.402 0.041,-0.61c-0.014,0.004 -0.027,0.007 -0.041,0.01c0,0 -3,0 -3.6,0c-1.5,0 -2.8,-0.6 -3.4,-1.8c-0.7,-1.3 -1,-3.5 -2.8,-4.7c-0.3,-0.2 -0.1,-0.5 0.5,-0.5c0.6,0.1 1.9,0.9 2.7,2c0.9,1.1 1.8,2 3.4,2c2.487,0 3.82,-0.125 4.622,-0.555c0.934,-1.389 2.227,-2.445 3.578,-2.445v-0.025c-5.668,-0.182 -9.289,-2.066 -10.975,-4.975c-3.665,0.042 -6.856,0.405 -8.677,0.707c-0.058,-0.327 -0.108,-0.656 -0.151,-0.987c1.797,-0.296 4.843,-0.647 8.345,-0.714c-0.112,-0.276 -0.209,-0.559 -0.291,-0.849c-3.511,-0.178 -6.541,-0.039 -8.187,0.097c-0.02,-0.332 -0.047,-0.663 -0.051,-0.999c1.649,-0.135 4.597,-0.27 8.018,-0.111c-0.079,-0.5 -0.13,-1.011 -0.13,-1.543c0,-1.7 0.6,-3.5 1.7,-5c-0.5,-1.7 -1.2,-5.3 0.2,-6.6c2.7,0 4.6,1.3 5.5,2.1c1.699,-0.701 3.599,-1.101 5.699,-1.101c2.1,0 4,0.4 5.6,1.1c0.9,-0.8 2.8,-2.1 5.5,-2.1c1.5,1.4 0.7,5 0.2,6.6c1.1,1.5 1.7,3.2 1.6,5c0,0.484 -0.045,0.951 -0.11,1.409c3.499,-0.172 6.527,-0.034 8.204,0.102c-0.002,0.337 -0.033,0.666 -0.051,0.999c-1.671,-0.138 -4.775,-0.28 -8.359,-0.089c-0.089,0.336 -0.197,0.663 -0.325,0.98c3.546,0.046 6.665,0.389 8.548,0.689c-0.043,0.332 -0.093,0.661 -0.151,0.987c-1.912,-0.306 -5.171,-0.664 -8.879,-0.682c-1.665,2.878 -5.22,4.755 -10.777,4.974v0.031c2.6,0 5,3.9 5,6.6v5.4c0,0.823 0.498,1.53 1.209,1.836c9.161,-3.032 15.791,-11.672 15.791,-21.836c0,-12.682 -10.317,-23 -23,-23c-12.683,0 -23,10.318 -23,23c0,10.164 6.63,18.804 15.791,21.836z"></path></g></g>
</svg>'''

def svg_to_png(svg_data, scale=1.0):
	# Requires cairosvg and pillow
	import cairosvg
	png_bytes = cairosvg.svg2png(bytestring=svg_data.encode('utf-8'), scale=scale)
	return Image.open(io.BytesIO(png_bytes))

class InstallerApp(ctk.CTk):
	def on_cancel(self):
		self.destroy()
	def __init__(self):
		super().__init__()
		self.title("Alterion Panel Installer")
		self.geometry("1200x800")
		self.resizable(False, False)
		# Set custom icon (Windows only)
		import os
		if os.name == 'nt':
			try:
				self.iconbitmap(os.path.join(os.path.dirname(__file__), "assets", "Alterion.ico"))
			except Exception:
				pass
		ctk.set_appearance_mode("dark")
		ctk.set_default_color_theme("dark-blue")

		self.selected_option = tk.StringVar(value="main")
		self.license_agreed = tk.BooleanVar(value=False)
		self.current_step = 1
		self._build_ui()

	def _build_ui(self):
		# Clear window
		for widget in self.winfo_children():
			widget.destroy()

		# Main container
		self.container = ctk.CTkFrame(self, fg_color="#282828", border_width=2, border_color="#444", corner_radius=8)
		self.container.pack(fill="both", expand=True, padx=0, pady=0)

		# Header
		header = ctk.CTkFrame(self.container, fg_color="#282828")
		header.pack(fill="x", pady=(32,0), padx=32)
		header.grid_columnconfigure(1, weight=1)

		# SVG Logo (rendered as PNG)
		try:
			logo_img = svg_to_png(LOGO_SVG, scale=1.0)
			self.logo_tk = ImageTk.PhotoImage(logo_img)
			logo_label = tk.Label(header, image=self.logo_tk, bg="#282828")
			logo_label.grid(row=0, column=0, sticky="w", rowspan=2, padx=(0, 16))
		except Exception:
			# Fallback to text logo if SVG render fails
			logo_label = ctk.CTkLabel(header, text="ALTERION\nPANEL", font=("Segoe UI", 48, "bold"), text_color="#e6f0f3", justify="left")
			logo_label.grid(row=0, column=0, sticky="w", rowspan=2)

		# Social box with icons
		social = ctk.CTkFrame(header, fg_color="#232323", width=180, height=60, corner_radius=4, border_width=1, border_color="#333")
		social.grid(row=0, column=1, padx=32)
		social.pack_propagate(False)

		def svg_icon_to_tk(svg, size=32):
			import cairosvg
			img = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode('utf-8'), output_width=size, output_height=size)))
			return ImageTk.PhotoImage(img)

		self.discord_icon = svg_icon_to_tk(DISCORD_SVG, 32)
		self.github_icon = svg_icon_to_tk(GITHUB_SVG, 32)

		def open_discord(_event=None):
			webbrowser.open_new_tab("https://discord.com/invite/8HEva3um2B")
		def open_github(_event=None):
			webbrowser.open_new_tab("https://github.com/Chace-Berry/Alterion_Panel")

		discord_btn = tk.Label(social, image=self.discord_icon, bg="#232323", cursor="hand2")
		discord_btn.pack(side="left", padx=(24,12), pady=8)
		discord_btn.bind("<Button-1>", open_discord)

		github_btn = tk.Label(social, image=self.github_icon, bg="#232323", cursor="hand2")
		github_btn.pack(side="left", padx=(12,24), pady=8)
		github_btn.bind("<Button-1>", open_github)

		# Version
		version = ctk.CTkLabel(header, text="V1.0.0", font=("Segoe UI", 20), text_color="#e6f0f3")
		version.grid(row=0, column=2, sticky="e", padx=(0,8))

		# Stepper logic
		if self.current_step == 1:
			self._build_step1()
		elif self.current_step == 2:
			self._build_license_step()
		elif self.current_step == 3:
			self._build_install_progress()

	def _add_radio_option(self, parent, text, value, idx):
		# Custom radio button look
		frame = ctk.CTkFrame(parent, fg_color="#232323", corner_radius=28, border_width=2, border_color="#232323")
		frame.grid(row=idx, column=0, pady=16, padx=0, sticky="ew")
		frame.grid_propagate(False)
		frame.configure(width=900, height=80)

		def select():
			self.selected_option.set(value)
			for child in parent.winfo_children():
				child.configure(border_color="#232323")
			frame.configure(border_color="#6e7b8b")

		# Radio circle
		radio_canvas = tk.Canvas(frame, width=36, height=36, bg="#232323", highlightthickness=0)
		radio_canvas.place(x=32, rely=0.5, anchor="w")
		circle = radio_canvas.create_oval(2,2,34,34, outline="#e6f0f3", width=4)
		dot = radio_canvas.create_oval(10,10,26,26, fill="#e6f0f3", outline="", state="hidden")

		def update_radio(*_):
			if self.selected_option.get() == value:
				frame.configure(border_color="#6e7b8b")
				radio_canvas.itemconfigure(dot, state="normal")
			else:
				frame.configure(border_color="#232323")
				radio_canvas.itemconfigure(dot, state="hidden")
		self.selected_option.trace_add("write", update_radio)
		frame.bind("<Button-1>", lambda e: select())
		radio_canvas.bind("<Button-1>", lambda e: select())

		label = ctk.CTkLabel(frame, text=text, font=("Segoe UI", 28), text_color="#e6f0f3")
		label.place(x=80, rely=0.5, anchor="w")
		label.bind("<Button-1>", lambda e: select())

		# Initial state
		if idx == 0:
			frame.configure(border_color="#6e7b8b")
			radio_canvas.itemconfigure(dot, state="normal")

	def _build_step1(self):
		# Step 1: Radio options
		step_frame = ctk.CTkFrame(self.container, fg_color="#282828")
		step_frame.pack(fill="both", expand=True, pady=(0,0))

		radio_group = ctk.CTkFrame(step_frame, fg_color="#282828")
		radio_group.place(relx=0.5, rely=0.35, anchor="center")

		self._add_radio_option(radio_group, "Install Main Panel", "main", 0)
		self._add_radio_option(radio_group, "Install Node", "node", 1)
		self._add_radio_option(radio_group, "Remote Install", "remote", 2)

		# Footer buttons (Next, then Cancel)
		footer = ctk.CTkFrame(self.container, fg_color="#282828")
		footer.pack(side="bottom", anchor="e", pady=32, padx=32, fill="x")
		footer.grid_columnconfigure(0, weight=1)
		next_btn = ctk.CTkButton(footer, text="Next", width=160, height=48, fg_color="#23253a", text_color="#e6f0f3", hover_color="#23253a", border_width=2, border_color="#23253a", corner_radius=16, font=("Segoe UI", 20), command=self._go_to_license)
		next_btn.pack(side="right", padx=(0,24))
		cancel_btn = ctk.CTkButton(footer, text="Cancel", width=160, height=48, fg_color="#353535", text_color="#e6f0f3", hover_color="#232323", border_width=2, border_color="#444", corner_radius=16, font=("Segoe UI", 20), command=self.on_cancel)
		cancel_btn.pack(side="right", padx=(0,0))

	def _go_to_license(self):
		self.current_step = 2
		self._build_ui()

	def _build_license_step(self):
		# License/TOS agreement screen
		license_text = (
			"""
				Alterion Public Use License (APUL)
					Version 2.0, 3 October 2025

 Copyright (C) 2025 Chace Berry

 All rights reserved. This software, including source code, assets, 
 documentation, and related materials (collectively, \"Software\"), 
 is the exclusive property of Chace Berry.

 Everyone is permitted to use, study, and modify this Software under 
 the conditions set forth below. Copying or redistributing this license 
 text itself is strictly prohibited.

	Preamble

 The Alterion Public Use License (APUL) is designed to protect the 
 ownership of Chace Berry while allowing the community to benefit 
 from using and modifying the Software. APUL guarantees freedom 
 to use and study the Software while enforcing attribution and 
 commercial-use conditions.

 You may run the Software for any purpose.

 You may study and modify the Software.

 You may share modified or unmodified versions only under the conditions 
 that they remain free and credit Chace Berry as the original creator.

	Terms and Conditions

0. Definitions.

 \"This License\" refers to APUL version 2.0.

 \"Copyright\" includes all copyright-like protections for the Software.

 \"The Program\" refers to any work licensed under APUL.

 \"You\" means the licensee or recipient of the Software.

 \"Modify\" means copying, adapting, or transforming the work beyond 
 a literal duplicate.

 \"Covered Work\" means the unmodified Program or any work derived from it.

 \"Convey\" means any act of distributing the Software or enabling others 
 to receive it.

1. Ownership.

 All rights, title, and interest in the Software remain with Chace Berry. 
 No one may claim ownership of the Software or any derivative work.

2. Free Use and Modification.

 You may:
	 - Use the Software for personal, educational, or research purposes.
	 - Modify the Software for any non-commercial purpose.
	 - Distribute modified or unmodified versions ONLY IF the work is 
		 free of charge and includes attribution to Chace Berry.

 Suggested attribution:
 "This software is based on work by Chace Berry (https://github.com/Chace-Berry)."

3. Commercial Use Clause.

 If you incorporate any part of the Software into proprietary or 
 commercial software:
	 - You MUST compensate Chace Berry thirty percent (30%) of gross 
		 revenue derived from that software on a monthly basis.
	 - Failure to comply constitutes a violation of this license and may 
		 result in legal action.

4. Attribution Requirement.

 All distributed versions of the Software, modified or unmodified, 
 must credit Chace Berry in source code, documentation, or user 
 interfaces where reasonable.

5. Prohibited Use.

 You MAY NOT:
	 - Claim the Software or any derivative work as your own.
	 - Remove, obscure, or alter copyright or license notices.
	 - Distribute derivative works as proprietary software without 
		 agreeing to the 30% revenue share.

6. Non-Source Distribution.

 Object code or compiled versions may be distributed only if the 
 Corresponding Source or an offer to provide it is included.

7. User Products.

 For consumer goods or products incorporating APUL Software:
	 - Installation information must be provided for modified versions 
		 to ensure users can exercise their rights.

8. Patents.

 Contributors grant non-exclusive, worldwide, royalty-free patent rights 
 for the Software. Patent licenses may not discriminate against users 
 or restrict the freedoms granted by this License.

9. Networked and Cloud Use.

 Running APUL Software on servers or in the cloud does not restrict 
 the freedoms of recipients.

10. Termination.

 Violating this License immediately terminates your rights. Rights 
 may be reinstated if violations cease and no repeated violations exist.

11. Disclaimer of Warranty.

 The Software is provided "as-is" without warranty of any kind. Use 
 at your own risk; authors are not liable for damages, losses, or liabilities.

12. Limitation of Liability.

 Authors or contributors are not liable for any direct, indirect, incidental, 
 or consequential damages resulting from use.

	How to Apply This License

 To apply APUL, attach the following notice to your source files:

 <Program Name> — <Brief Description>
 Copyright (C) 2025 Chace Berry

 This program is free software: you can redistribute it and/or modify 
 it under the terms of the Alterion Public Use License (APUL) version 2.0.

 This program is distributed in the hope that it will be useful, 
 but WITHOUT ANY WARRANTY.

 For interactive programs, display a short notice at startup:

 <Program Name> — Copyright (C) 2025 Chace Berry
 This program comes with ABSOLUTELY NO WARRANTY.
 It is free software under the Alterion Public Use License (APUL).
"""
		)
		frame = ctk.CTkFrame(self.container, fg_color="#282828")
		frame.pack(fill="both", expand=True, pady=(0,0))

		tos_box = ctk.CTkTextbox(frame, width=900, height=320, font=("Segoe UI", 18), fg_color="#232323", text_color="#e6f0f3")
		tos_box.insert("1.0", license_text)
		tos_box.configure(state="disabled")
		tos_box.place(relx=0.5, rely=0.3, anchor="center")

		agree_chk = ctk.CTkCheckBox(frame, text="I agree to the License and Terms of Service", variable=self.license_agreed, font=("Segoe UI", 18), text_color="#e6f0f3")
		agree_chk.place(relx=0.5, rely=0.6, anchor="center")

		# Footer
		footer = ctk.CTkFrame(self.container, fg_color="#282828")
		footer.pack(side="bottom", anchor="e", pady=32, padx=32, fill="x")
		footer.grid_columnconfigure(0, weight=1)
		next_btn = ctk.CTkButton(footer, text="Install", width=160, height=48, fg_color="#23253a", text_color="#e6f0f3", hover_color="#23253a", border_width=2, border_color="#23253a", corner_radius=16, font=("Segoe UI", 20), command=self._license_next)
		next_btn.pack(side="right", padx=(0,24))
		cancel_btn = ctk.CTkButton(footer, text="Cancle", width=160, height=48, fg_color="#353535", text_color="#e6f0f3", hover_color="#232323", border_width=2, border_color="#444", corner_radius=16, font=("Segoe UI", 20), command=self.on_cancel)
		cancel_btn.pack(side="right", padx=(0,0))

	def _license_next(self):
		if not self.license_agreed.get():
			from tkinter import messagebox
			messagebox.showerror("Agreement Required", "You must agree to the License and Terms of Service to continue.")
			return
		self.current_step = 3
		self._build_ui()

	def _build_install_progress(self):
		# Install progress bar screen (placeholder, will call install logic)
		frame = ctk.CTkFrame(self.container, fg_color="#282828")
		frame.pack(fill="both", expand=True, pady=(0,0))

		self.progress_label = ctk.CTkLabel(frame, text="Preparing to install...", font=("Segoe UI", 22), text_color="#e6f0f3")
		self.progress_label.place(relx=0.5, rely=0.4, anchor="center")

		self.progress_bar = ctk.CTkProgressBar(frame, width=600, height=32)
		self.progress_bar.place(relx=0.5, rely=0.5, anchor="center")
		self.progress_bar.set(0)

		# Footer with Cancel and Next buttons
		footer = ctk.CTkFrame(self.container, fg_color="#282828")
		footer.pack(side="bottom", anchor="e", pady=32, padx=32, fill="x")
		footer.grid_columnconfigure(0, weight=1)
		self.next_btn = ctk.CTkButton(footer, text="Next", width=160, height=48, fg_color="#23253a", text_color="#e6f0f3", hover_color="#23253a", border_width=2, border_color="#23253a", corner_radius=16, font=("Segoe UI", 20), command=self._install_next, state="disabled")
		self.next_btn.pack(side="right", padx=(0,24))
		cancel_btn = ctk.CTkButton(footer, text="Cancel", width=160, height=48, fg_color="#353535", text_color="#e6f0f3", hover_color="#232323", border_width=2, border_color="#444", corner_radius=16, font=("Segoe UI", 20), command=self.on_cancel)
		cancel_btn.pack(side="right", padx=(0,0))

		self.after(500, self._start_install)

	def _install_next(self):
		# Placeholder for what happens after install (e.g., close or next step)
		self.destroy()

	def _start_install(self):
		if self.selected_option.get() == "main":
			self._install_main_panel()
		elif self.selected_option.get() == "node":
			self._install_node_agent()
		# TODO: Add remote flow

	def _install_node_agent(self):
		import threading
		def run():
			try:
				self._set_progress(0.05, "Checking for latest node agent release...")
				import requests, os, subprocess
				from tkinter import messagebox

				GITHUB_API = "https://api.github.com/repos/Chace-Berry/Alterion_Panel/releases/latest"
				INSTALL_DIR = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Chace-Berry", "Alterion", "Alterion_panel")
				os.makedirs(INSTALL_DIR, exist_ok=True)
				exe_path = os.path.join(INSTALL_DIR, "node_agent.exe")
				# Check if already installed
				if os.path.exists(exe_path):
					res = messagebox.askyesno("Node Agent Already Installed", "node_agent.exe is already installed. Do you want to overwrite it?")
					if not res:
						self._set_progress(1.0, "Node agent install skipped.")
						self.next_btn.configure(state="normal")
						return

				resp = requests.get(GITHUB_API, timeout=10)
				resp.raise_for_status()
				release = resp.json()
				assets = release.get("assets", [])
				asset = next((a for a in assets if a["name"].lower() == "node_agent.exe"), None)
				if not asset:
					self._set_progress(0, "No node_agent.exe asset found in latest release.")
					messagebox.showerror("Install Failed", "No node_agent.exe asset found in latest release.")
					return
				url = asset["browser_download_url"]
				filename = asset["name"]
				self._set_progress(0.15, f"Downloading {filename}...")
				with requests.get(url, stream=True) as r:
					r.raise_for_status()
					total = int(r.headers.get('content-length', 0))
					downloaded = 0
					with open(exe_path, "wb") as f:
						for chunk in r.iter_content(chunk_size=8192):
							if chunk:
								f.write(chunk)
								downloaded += len(chunk)
								if total:
									self._set_progress(0.15 + 0.7 * (downloaded/total), f"Downloading {filename}...")
				self._set_progress(0.9, "Launching node agent...")
				try:
					subprocess.Popen([exe_path], cwd=INSTALL_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
				except Exception:
					pass
				self._set_progress(1.0, "Node agent installed and running!")
				self.next_btn.configure(state="normal")
				messagebox.showinfo("Success", f"node_agent.exe installed and running in background at:\n{INSTALL_DIR}")
			except Exception as e:
				self._set_progress(0, f"Install Failed: {e}")
				from tkinter import messagebox
				messagebox.showerror("Install Failed", str(e))

		threading.Thread(target=run, daemon=True).start()

	def _install_main_panel(self):
		import threading
		def run():
			try:
				self._set_progress(0.05, "Checking for latest release...")
				import requests, os, zipfile, tempfile, shutil, sys, ctypes
				from tkinter import messagebox

				GITHUB_API = "https://api.github.com/repos/Chace-Berry/Alterion_Panel/releases/latest"
				INSTALL_DIR = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Chace-Berry", "Alterion", "Alterion_panel")
				os.makedirs(INSTALL_DIR, exist_ok=True)
				exe_path = os.path.join(INSTALL_DIR, "AlterionPanel.exe")
				# Check if already installed
				if os.path.exists(exe_path):
					res = messagebox.askyesno("Alterion Panel Already Installed", "AlterionPanel.exe is already installed. Do you want to overwrite it?")
					if not res:
						self._set_progress(1.0, "Alterion Panel install skipped.")
						self.next_btn.configure(state="normal")
						return

				resp = requests.get(GITHUB_API, timeout=10)
				resp.raise_for_status()
				release = resp.json()
				assets = release.get("assets", [])
				asset = next((a for a in assets if a["name"].endswith(".exe")), None)
				if not asset:
					asset = next((a for a in assets if a["name"].endswith(".zip")), None)
				if not asset:
					self._set_progress(0, "No .exe or .zip asset found in latest release.")
					messagebox.showerror("Install Failed", "No .exe or .zip asset found in latest release.")
					return
				url = asset["browser_download_url"]
				filename = asset["name"]
				self._set_progress(0.15, f"Downloading {filename}...")
				tmp = tempfile.NamedTemporaryFile(delete=False)
				with requests.get(url, stream=True) as r:
					r.raise_for_status()
					total = int(r.headers.get('content-length', 0))
					downloaded = 0
					for chunk in r.iter_content(chunk_size=8192):
						if chunk:
							tmp.write(chunk)
							downloaded += len(chunk)
							if total:
								self._set_progress(0.15 + 0.7 * (downloaded/total), f"Downloading {filename}...")
				tmp.close()
				self._set_progress(0.9, "Installing...")
				if filename.endswith(".exe"):
					shutil.move(tmp.name, os.path.join(INSTALL_DIR, filename))
				elif filename.endswith(".zip"):
					with zipfile.ZipFile(tmp.name, 'r') as zip_ref:
						zip_ref.extractall(INSTALL_DIR)
					os.unlink(tmp.name)
				self._set_progress(1.0, "Install complete!")
				# Enable Next button after install
				self.next_btn.configure(state="normal")
				messagebox.showinfo("Success", f"Alterion Panel installed to:\n{INSTALL_DIR}")
			except Exception as e:
				self._set_progress(0, f"Install Failed: {e}")
				from tkinter import messagebox
				messagebox.showerror("Install Failed", str(e))

		threading.Thread(target=run, daemon=True).start()

	def _set_progress(self, value, msg):
		self.progress_bar.set(value)
		self.progress_label.configure(text=msg)


# Launch the installer window if run as a script
if __name__ == "__main__":
	import ctypes
	def get_latest_installer_version():
		try:
			api = "https://api.github.com/repos/Chace-Berry/Alterion_Panel/releases/latest"
			resp = requests.get(api, timeout=10)
			resp.raise_for_status()
			release = resp.json()
			tag = release.get("tag_name") or release.get("name")
			assets = release.get("assets", [])
			exe_asset = next((a for a in assets if a["name"].lower().startswith("installer") and a["name"].endswith(".exe")), None)
			url = exe_asset["browser_download_url"] if exe_asset else None
			return tag, url
		except Exception:
			return None, None

	def get_current_version():
		# Extract from version label in UI or hardcode here
		return "V1.0.0"

	def self_update_and_relaunch():
		tag, url = get_latest_installer_version()
		current = get_current_version().lstrip("vV")
		if tag and url and tag.lstrip("vV") != current:
			# Download new installer
			tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".exe")
			with requests.get(url, stream=True) as r:
				r.raise_for_status()
				for chunk in r.iter_content(chunk_size=8192):
					if chunk:
						tmp.write(chunk)
			tmp.close()
			# Launch new installer with --noupdate flag and exit
			import subprocess
			subprocess.Popen([tmp.name, "--noupdate"], close_fds=True)
			sys.exit(0)

	if os.name == 'nt':
		# Only run self-update if --noupdate is not present
		if '--noupdate' not in sys.argv:
			self_update_and_relaunch()
		try:
			is_admin = ctypes.windll.shell32.IsUserAnAdmin()
		except Exception:
			is_admin = False
		if not is_admin:
			exe_path = sys.executable
			if exe_path.lower().endswith(("python.exe", "pythonw.exe")):
				pythonw = exe_path.replace("python.exe", "pythonw.exe")
				if not os.path.exists(pythonw):
					pythonw = exe_path
				params = ' '.join([f'"{arg}"' for arg in sys.argv])
				ctypes.windll.shell32.ShellExecuteW(None, "runas", pythonw, params, None, 0)
			else:
				# Preserve --noupdate flag if present
				params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
				ctypes.windll.shell32.ShellExecuteW(None, "runas", exe_path, params, None, 1)
			sys.exit(0)
	app = InstallerApp()
	app.mainloop()
