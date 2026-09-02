import { useEffect, useRef } from "react";

type BackdropCanvasProps = {
	kind: "mesh" | "aurora" | "grain";
};

const FRAGMENT_SHADER = `
precision mediump float;
uniform vec2 u_resolution;
uniform float u_time;
uniform vec2 u_pointer;
uniform float u_scroll;
uniform vec3 u_background;
uniform vec3 u_primary;
uniform vec3 u_accent;
uniform float u_mode;
uniform float u_seed;

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float blob(vec2 st, vec2 center, float radius) {
	return smoothstep(radius, 0.0, distance(st, center));
}

void main() {
	vec2 st = gl_FragCoord.xy / u_resolution;
	st.x *= u_resolution.x / u_resolution.y;
	float t = u_time * (u_mode > 1.5 ? 0.05 : 0.12) + u_seed * 37.0;
	float drift = u_scroll * 0.15;

	vec2 c1 = vec2(0.25 + 0.3 * sin(t * 0.9 + u_seed * 9.0), 0.72 + 0.2 * cos(t * 0.7 + u_seed * 5.0) - drift);
	vec2 c2 = vec2(1.05 + 0.28 * cos(t * 0.6 + u_seed * 3.0), 0.3 + 0.24 * sin(t * 0.8 + u_seed * 7.0) - drift * 0.6);
	vec2 c3 = vec2(0.6 + 0.32 * sin(t * 0.5 + 2.0 + u_seed * 11.0), 0.85 + 0.18 * cos(t * 1.1 + u_seed * 4.0) - drift * 0.8);
	vec2 pointer = vec2(u_pointer.x * (u_resolution.x / u_resolution.y), 1.0 - u_pointer.y);

	float softness = (u_mode > 0.5 ? 0.95 : 0.62) + 0.18 * fract(u_seed * 13.7);
	float w1 = blob(st, c1, softness);
	float w2 = blob(st, c2, softness * 0.9);
	float w3 = blob(st, c3, softness * 1.05);
	float wp = blob(st, pointer, 0.5) * 0.5;

	vec3 color = u_background;
	color = mix(color, u_primary, w1 * 0.5);
	color = mix(color, u_accent, w2 * 0.42);
	color = mix(color, mix(u_primary, u_accent, 0.5), w3 * 0.3);
	color = mix(color, u_accent, wp * 0.35);

	if (u_mode > 1.5) {
		float noise = hash(gl_FragCoord.xy + fract(u_time) * 61.0);
		color = mix(color, u_background, 0.35);
		color += (noise - 0.5) * 0.07;
	}

	gl_FragColor = vec4(color, 1.0);
}
`;

const VERTEX_SHADER = "attribute vec2 a_position; void main() { gl_Position = vec4(a_position, 0.0, 1.0); }";

function cssColorToRGB(value: string): [number, number, number] {
	const probe = document.createElement("div");
	probe.style.color = value;
	document.body.appendChild(probe);
	const resolved = getComputedStyle(probe).color;
	document.body.removeChild(probe);
	const channels = resolved.match(/[\d.]+/g);
	if (!channels || channels.length < 3) return [1, 1, 1];
	const scale = resolved.startsWith("color(") ? 1 : 255;
	return [Number(channels[0]) / scale, Number(channels[1]) / scale, Number(channels[2]) / scale];
}

function siteSeed(): number {
	const identity = document.title + location.host + location.pathname;
	let hash = 0;
	for (let index = 0; index < identity.length; index += 1) {
		hash = (hash * 31 + identity.charCodeAt(index)) >>> 0;
	}
	return (hash % 1000) / 1000;
}

function themeColor(variable: string): [number, number, number] {
	const value = getComputedStyle(document.documentElement).getPropertyValue(variable).trim();
	return cssColorToRGB(value || "#ffffff");
}

export function BackdropCanvas({ kind }: BackdropCanvasProps) {
	const canvasReference = useRef<HTMLCanvasElement>(null);

	useEffect(() => {
		const canvas = canvasReference.current;
		if (!canvas) return;
		const gl = canvas.getContext("webgl", { antialias: false, depth: false });
		if (!gl) return;
		const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

		const program = gl.createProgram();
		const vertexShader = gl.createShader(gl.VERTEX_SHADER);
		const fragmentShader = gl.createShader(gl.FRAGMENT_SHADER);
		if (!program || !vertexShader || !fragmentShader) return;
		gl.shaderSource(vertexShader, VERTEX_SHADER);
		gl.compileShader(vertexShader);
		gl.shaderSource(fragmentShader, FRAGMENT_SHADER);
		gl.compileShader(fragmentShader);
		if (!gl.getShaderParameter(fragmentShader, gl.COMPILE_STATUS)) return;
		gl.attachShader(program, vertexShader);
		gl.attachShader(program, fragmentShader);
		gl.linkProgram(program);
		gl.useProgram(program);

		const buffer = gl.createBuffer();
		gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
		gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
		const positionLocation = gl.getAttribLocation(program, "a_position");
		gl.enableVertexAttribArray(positionLocation);
		gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0);

		const uniforms = {
			resolution: gl.getUniformLocation(program, "u_resolution"),
			time: gl.getUniformLocation(program, "u_time"),
			pointer: gl.getUniformLocation(program, "u_pointer"),
			scroll: gl.getUniformLocation(program, "u_scroll"),
			background: gl.getUniformLocation(program, "u_background"),
			primary: gl.getUniformLocation(program, "u_primary"),
			accent: gl.getUniformLocation(program, "u_accent"),
			mode: gl.getUniformLocation(program, "u_mode"),
			seed: gl.getUniformLocation(program, "u_seed"),
		};

		const heroBackground = themeColor("--hero-background");
		const primary = themeColor("--primary");
		const accent = themeColor("--accent");
		gl.uniform3fv(uniforms.background, heroBackground);
		gl.uniform3fv(uniforms.primary, primary);
		gl.uniform3fv(uniforms.accent, accent);
		gl.uniform1f(uniforms.mode, kind === "mesh" ? 0 : kind === "aurora" ? 1 : 2);
		gl.uniform1f(uniforms.seed, siteSeed());

		const pointer = { x: 0.7, y: 0.3, targetX: 0.7, targetY: 0.3 };
		let scrollOffset = 0;
		let animationFrame = 0;
		let startTime = performance.now();

		const resize = () => {
			const ratio = Math.min(window.devicePixelRatio || 1, 1.5);
			const bounds = canvas.getBoundingClientRect();
			canvas.width = Math.max(1, Math.round(bounds.width * ratio));
			canvas.height = Math.max(1, Math.round(bounds.height * ratio));
			gl.viewport(0, 0, canvas.width, canvas.height);
			gl.uniform2f(uniforms.resolution, canvas.width, canvas.height);
		};

		const onPointerMove = (event: PointerEvent) => {
			const bounds = canvas.getBoundingClientRect();
			pointer.targetX = (event.clientX - bounds.left) / Math.max(1, bounds.width);
			pointer.targetY = (event.clientY - bounds.top) / Math.max(1, bounds.height);
		};

		const onScroll = () => {
			scrollOffset = Math.min(1, window.scrollY / Math.max(1, window.innerHeight));
		};

		const draw = () => {
			pointer.x += (pointer.targetX - pointer.x) * 0.05;
			pointer.y += (pointer.targetY - pointer.y) * 0.05;
			gl.uniform1f(uniforms.time, (performance.now() - startTime) / 1000);
			gl.uniform2f(uniforms.pointer, pointer.x, pointer.y);
			gl.uniform1f(uniforms.scroll, scrollOffset);
			gl.drawArrays(gl.TRIANGLES, 0, 3);
			if (!prefersReducedMotion) animationFrame = requestAnimationFrame(draw);
		};

		resize();
		draw();
		window.addEventListener("resize", resize);
		if (!prefersReducedMotion) {
			window.addEventListener("pointermove", onPointerMove);
			window.addEventListener("scroll", onScroll, { passive: true });
		}
		return () => {
			cancelAnimationFrame(animationFrame);
			window.removeEventListener("resize", resize);
			window.removeEventListener("pointermove", onPointerMove);
			window.removeEventListener("scroll", onScroll);
		};
	}, [kind]);

	return <canvas ref={canvasReference} className="backdrop-canvas" aria-hidden="true" />;
}
