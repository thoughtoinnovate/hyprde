#version 300 es
precision mediump float;
in vec2 v_texcoord;
uniform sampler2D tex;
out vec4 fragColor;

void main() {
    vec4 pix = texture(tex, v_texcoord);
    
    // Reduce blue and slightly reduce green to create a warm "RedGlow" effect
    pix.g *= 0.85;
    pix.b *= 0.60;
    
    fragColor = pix;
}
