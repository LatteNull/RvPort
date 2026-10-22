BASE_FLAGS = -DUSE_AVX2=1
CPPFLAGS = $(BASE_FLAGS)
CPPFLAGS += -D UNUSED=0

main.o: main.cpp wrapper.h
	$(CXX) $(CPPFLAGS) -c main.cpp -o main.o
