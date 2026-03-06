const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    const exe = b.addExecutable(.{
        .name = "hyprsearch",
        .root_module = b.createModule(.{
            .target = target,
            .optimize = optimize,
        }),
    });

    exe.addCSourceFile(.{ .file = b.path("src/launcher.c"), .flags = &.{} });
    exe.linkLibC();
    exe.linkSystemLibrary("gtk+-3.0");
    exe.linkSystemLibrary("gtk-layer-shell-0");
    exe.linkSystemLibrary("gio-2.0");

    b.installArtifact(exe);
}